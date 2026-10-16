/* 文件职责：Wi-Fi 模块与 PC 网关的双向数据通道。
 * 主要功能：非阻塞 AT 连接、限时重连、认证握手、命令和规则写入同一控制信箱。
 * 技术栈：C、HAL 时钟、USART3、MB026、换行帧；模块联动：demo 本地保护、hardware_control、gateway.server。
 * 编写/修改日期（日志对应）：2026-10-16（供气演示与验收）；2026-09-30、2026-10-02、2026-10-15。 */
#include "kitchen_wifi.h"
#include "hardware_control.h"
#include "hardware_status.h"
#include "sample_spool.h"
#include "./BSP/ATK_MB026/atk_mb026.h"
#include "./BSP/ATK_MB026/atk_mb026_uart.h"
#include <stdio.h>
#include <string.h>
volatile KitchenWifiConfig g_wifi_config = {0x4649534Bu};
static uint32_t stage, deadline, last_reply;
static char rx_line[220];
static uint16_t rx_length;
/* 最后一页专门存无线配置，Keil 链接区缩至 63 KiB，避免应用代码覆盖。
 * 配置带完整性校验，只在待机且修订变更时写一次；掉电后仍须人员显式启用采样。 */
#define WIFI_STORAGE 0x0800FC00u
static uint32_t storage_checked, saved_revision;

/* 功能：用有符号差值保护同轮时间进位及 32 位回绕；心跳间隔远小于半个计数周期。
 * 输入：当前毫秒与上次回应毫秒；输出：是否仍在十秒有效窗。日期：2026-10-15。 */
static uint8_t reply_recent(uint32_t now, uint32_t reply)
{
    return (int32_t)(now - reply) < 10000;
}

/* 功能：板上验证同轮晚一毫秒、计数回绕和真实超时，防止误触发重连回归。
 * 输入无；输出失败位；模块联动：demo 合并到算法自检结果。日期：2026-10-15。 */
uint32_t kitchen_wifi_self_test(void)
{
    uint32_t failures = 0u;
    if (!reply_recent(1000u, 1001u)) failures |= 1u;
    if (!reply_recent(5u, 0xFFFFFFF0u)) failures |= 2u;
    if (reply_recent(20000u, 0u)) failures |= 4u;
    return failures;
}

/* 功能：为有界配置计算完整性摘要，拒绝断电造成的半写页；不用于替代网络认证。
 * 输入：固定 196 字节配置；输出：FNV-1a 校验值。日期：2026-10-15。 */
static uint32_t config_checksum(const uint8_t *bytes, uint32_t length)
{
    uint32_t value = 2166136261u, i;
    for (i = 0; i < length; i++) value = (value ^ bytes[i]) * 16777619u;
    return value;
}

/* 功能：恢复或保存私有热点参数；只在待机更改 Flash，不写入采样启用状态。
 * 输入来自 SWD 私有配置；输出为专用 Flash 页，答辩工程和 HEX 不含此页。
 * 模块联动：Keil IROM 边界、g_wifi_config 与本机配置页面；日期：2026-10-15。 */
static void config_storage(void)
{
    const uint32_t words = sizeof(KitchenWifiConfig) / 4u;
    static uint32_t image[sizeof(KitchenWifiConfig) / 4u + 1u];
    uint32_t i, error;
    if (!storage_checked) {
        const KitchenWifiConfig *stored = (const KitchenWifiConfig *)WIFI_STORAGE;
        storage_checked = 1u;
        if (stored->magic == 0x4649534Bu && stored->revision &&
            config_checksum((const uint8_t *)stored, sizeof(KitchenWifiConfig)) == ((const uint32_t *)WIFI_STORAGE)[words] &&
            stored->ssid[32] == 0 && stored->password[64] == 0 && stored->host[15] == 0 && stored->token[64] == 0) {
            memcpy((void *)&g_wifi_config, stored, sizeof(KitchenWifiConfig));
            saved_revision = g_wifi_config.revision;
            g_wifi_config.applied_revision = 0u; g_wifi_config.state = 0u;
        }
    }
    if (!g_wifi_config.revision || saved_revision == g_wifi_config.revision || g_hardware_status.monitoring_enabled) return;
    memcpy(image, (const void *)&g_wifi_config, sizeof(KitchenWifiConfig));
    image[2] = image[3] = 0u;
    image[words] = config_checksum((const uint8_t *)image, sizeof(KitchenWifiConfig));
    if (HAL_FLASH_Unlock() == HAL_OK) {
        FLASH_EraseInitTypeDef erase = {0};
        erase.TypeErase = FLASH_TYPEERASE_PAGES; erase.PageAddress = WIFI_STORAGE; erase.NbPages = 1u;
        if (HAL_FLASHEx_Erase(&erase, &error) == HAL_OK) {
            for (i = 0; i <= words; i++) if (HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, WIFI_STORAGE + i * 4u, image[i]) != HAL_OK) break;
            if (i > words) saved_revision = g_wifi_config.revision;
            sample_spool_preserve_boot();
        }
        HAL_FLASH_Lock();
    }
}

/* 功能：发送有界 AT 指令并设置下一阶段；密码只在模块串口传输，不写调试串口或日志。
 * 输入：指令、下一阶段、超时毫秒；联动：step 定期检查响应，不阻塞 ADC。日期：2026-10-15。 */
static void at(const char *cmd, uint32_t next, uint32_t timeout)
{
    atk_mb026_uart_rx_restart();
    atk_mb026_uart_send((const uint8_t *)cmd, (uint16_t)strlen(cmd));
    stage = next; deadline = HAL_GetTick() + timeout;
}

/* 功能：解析来自已建立 TCP 连接的紧凑命令；只接受完整行和有效动作范围。
 * 输入：C,序号,动作 或 R,版本,三个阈值；输出：信箱最后提交序号，固件依旧执行危险校验。
 * 模块联动：gateway.server → hardware_control → demo；日期：2026-10-02、2026-10-15。 */
static void control_line(const char *line)
{
    unsigned long a, b, c, d, e, f, g, h;
    char tail;
    if (!strcmp(line, "K")) { last_reply = HAL_GetTick(); return; }
    /* 日期：2026-10-15。A确认必须在服务器事务提交后返回；T校时不代表硬件有RTC。 */
    if (sscanf(line,"A,%lu,%lu%c",&a,&b,&tail)==2) {sample_spool_ack((uint32_t)a,(uint32_t)b);last_reply=HAL_GetTick();return;}
    if (sscanf(line,"T,%lu%c",&a,&tail)==1) {sample_spool_time((uint32_t)a);return;}
    if (sscanf(line, "C,%lu,%lu%c", &a, &b, &tail) == 2 && a && b >= 1u && b <= 17u) {
        if ((uint32_t)a != g_hardware_control.ack_sequence) {
            g_hardware_control.action = (uint32_t)b;
            __DMB(); g_hardware_control.request_sequence = (uint32_t)a;
        }
    } else if (sscanf(line, "R,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu%c", &a, &b, &c, &d, &e, &f, &g, &h, &tail) == 8) {
        g_hardware_control.gas_threshold = (uint32_t)b;
        g_hardware_control.smoke_threshold = (uint32_t)c;
        g_hardware_control.temperature_centi = (uint32_t)d;
        /* 2026-10-16：完整校验八字段后才提交规则，不接收截断行。 */
        g_hardware_control.supply_demo_enabled=(uint32_t)e;g_hardware_control.supply_low_threshold=(uint32_t)f;
        g_hardware_control.supply_settle_ms=(uint32_t)g;g_hardware_control.supply_hold_ms=(uint32_t)h;
        __DMB(); g_hardware_control.rule_revision = (uint32_t)a;
    }
}

/* 功能：逐段拼接透传数据，兼容一帧多行和一行分多帧；超长行整行丢弃，不能执行截断指令。
 * 输入：UART 缓冲；输出：完整控制行。模块联动：中断接收与 control_line；日期：2026-10-15。 */
static void consume(const char *data)
{
    while (*data) {
        char ch = *data++;
        if (ch == '\n') {
            if (rx_length < sizeof(rx_line) - 1u) { rx_line[rx_length] = 0; control_line(rx_line); }
            rx_length = 0u;
        } else if (ch != '\r' && rx_length < sizeof(rx_line) - 1u) rx_line[rx_length++] = ch;
    }
}

/* 功能：以独立步骤控制复位、AT、入网和 TCP，失败在十五秒后重试。
 * 输出：state 为可读失败阶段；连接后十秒没有 PC 心跳就重连，保护循环不等待网络。
 * 模块联动：本机 RAM 配置、MB026 与 gateway.server；日期：2026-10-15。 */
void kitchen_wifi_step(void)
{
    uint32_t now = HAL_GetTick();
    char cmd[220];
    uint8_t *frame;
    uint8_t ok = 0u, error = 0u;
    uint8_t chunk[129];uint16_t taken;static uint32_t seen_overruns;
    /* 连续流溢出后丢弃至换行边界，禁止把半条命令解释为另一条合法动作。 */
    if(seen_overruns!=atk_mb026_uart_stream_overruns()) {seen_overruns=atk_mb026_uart_stream_overruns();rx_length=sizeof(rx_line)-1u;}
    while((taken=atk_mb026_uart_stream_read(chunk,128u))!=0u) {chunk[taken]=0u;if(stage==9u) consume((const char *)chunk);}
    config_storage();
    if (!g_wifi_config.revision || !g_wifi_config.ssid[0] || !g_wifi_config.host[0]) return;
    if (g_wifi_config.applied_revision != g_wifi_config.revision) {
        GPIO_InitTypeDef gpio = {0};
        __HAL_RCC_GPIOA_CLK_ENABLE();
        gpio.Pin = GPIO_PIN_4; gpio.Mode = GPIO_MODE_OUTPUT_PP; gpio.Speed = GPIO_SPEED_FREQ_LOW;
        HAL_GPIO_Init(GPIOA, &gpio);
        atk_mb026_uart_init(115200);
        g_wifi_config.applied_revision = g_wifi_config.revision;
        stage = 0u; deadline = 0u;
    }
    frame = atk_mb026_uart_rx_get_frame();
    if (frame) {
        if (stage != 9u) {
            ok = strstr((const char *)frame, "OK") != 0;
            error = strstr((const char *)frame, "ERROR") != 0 || strstr((const char *)frame, "FAIL") != 0;
        }
        atk_mb026_uart_rx_restart();
    }
    /* 2026-10-15：consume 更新心跳时 HAL 毫秒可能刚进位。必须刷新 now，
     * 否则旧 now 减新 last_reply 的无符号下溢会被误判为十秒断网。 */
    now = HAL_GetTick();
    if (stage == 0u) {
        if (deadline && (int32_t)(deadline - now) > 0) return;
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET);
        stage = 1u; deadline = now + 150u; g_wifi_config.state = 1u;
    } else if (stage == 1u && (int32_t)(now - deadline) >= 0) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
        stage = 2u; deadline = now + 1500u;
    } else if (stage == 2u && (int32_t)(now - deadline) >= 0) at("AT\r\n", 3u, 3000u);
    else if (stage == 3u && ok) at("ATE0\r\n", 4u, 2000u);
    else if (stage == 4u && ok) at("AT+CWMODE=1\r\n", 5u, 3000u);
    else if (stage == 5u && ok) {
        snprintf(cmd, sizeof(cmd), "AT+CWJAP=\"%s\",\"%s\"\r\n", (const char *)g_wifi_config.ssid, (const char *)g_wifi_config.password);
        at(cmd, 6u, 20000u);
    } else if (stage == 6u && ok) {
        snprintf(cmd, sizeof(cmd), "AT+CIPSTART=\"TCP\",\"%s\",9000\r\n", (const char *)g_wifi_config.host);
        at(cmd, 7u, 8000u);
    } else if (stage == 7u && ok) at("AT+CIPMODE=1\r\n", 8u, 3000u);
    else if (stage == 8u && ok) at("AT+CIPSEND\r\n", 10u, 3000u);
    else if (stage == 10u && (ok || (int32_t)(now - deadline) >= 0)) {
        snprintf(cmd, sizeof(cmd), "{\"type\":\"hello\",\"token\":\"%s\"}\r\n", (const char *)g_wifi_config.token);
        atk_mb026_uart_send((const uint8_t *)cmd, (uint16_t)strlen(cmd));
        stage = 9u; last_reply = now;
    } else if (stage == 9u && reply_recent(now, last_reply)) {
        g_wifi_config.state = 5u;
    } else if (error || (stage != 9u && stage >= 3u && (int32_t)(now - deadline) >= 0) || (stage == 9u && !reply_recent(now, last_reply))) {
        g_wifi_config.state = stage <= 5u ? 2u : stage == 6u ? 3u : 4u;
        stage = 0u; deadline = now + 15000u; rx_length = 0u;
    }
}

/* 功能：仅在完成透传和 PC 心跳后发送遥测，不通过无线连接状态影响本地自动保护。
 * 输入：完整有界 JSON 行；模块联动：demo 与 UART；日期：2026-09-30、2026-10-15。 */
void kitchen_wifi_send(const char *text, uint16_t length)
{
    if (stage == 9u) atk_mb026_uart_send((const uint8_t *)text, length);
}

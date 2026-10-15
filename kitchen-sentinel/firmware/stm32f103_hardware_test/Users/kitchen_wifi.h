/* 文件职责：MB026 双向通信配置与状态接口。
 * 主要功能：接收本机配置、非阻塞连接、解析控制与规则、保持心跳。
 * 技术栈：C、USART3、AT 指令状态机、TCP 透传；模块联动：demo、SWD 配置、gateway.server。
 * 编写/修改日期（日志对应）：2026-09-30、2026-10-02、2026-10-15。 */
#ifndef KITCHEN_WIFI_H
#define KITCHEN_WIFI_H
#include <stdint.h>
/* 字符区固定偏移供 SWD 设置，配置仅在 RAM，不把热点密码放入可分发工程。 */
typedef struct {
    uint32_t magic, revision, applied_revision, state;
    char ssid[33], password[65], host[16], token[65];
} KitchenWifiConfig;
extern volatile KitchenWifiConfig g_wifi_config;
/* 每轮调用推进网络，不等待热点或 TCP；本地保护循环持续执行。 */
void kitchen_wifi_step(void);
/* 已连接时发送一行遥测；未连接直接返回。 */
void kitchen_wifi_send(const char *text, uint16_t length);
/* 验证毫秒进位、回绕与真正超时，不连接网络或操作输出；0 表示边界检查通过。 */
uint32_t kitchen_wifi_self_test(void);
#endif

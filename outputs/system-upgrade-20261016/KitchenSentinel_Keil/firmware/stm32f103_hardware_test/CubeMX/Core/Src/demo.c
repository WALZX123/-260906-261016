/*
 * 文件职责：传感器采集与本地显示、保护的主程序。
 * 主要功能：轮询四路 ADC 和两路 DO，滤波换算、判断危险、刷新 OLED，更新 SWD 状态并发送遥测。
 * 技术栈：C、HAL ADC/GPIO/TIM3、八点均值、NTC 公式、USART、MB026 TCP。
 * 模块联动：sensor_processing 计算数值，response_policy 决定保护，hardware_status 提供状态，Python 网关接入 PC；PB0 蜂鸣器、PA6 舵机、PA2/PA3 OLED。
 * 编写/修改日期（日志对应）：2026-10-15（启用、演练及无线联调）、2026-09-21、2026-09-23、2026-09-24、2026-09-30；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
/**
 * 厨房安全监测硬件测试入口。
 * 日志对应：2026-09-21 多传感器采集；2026-09-24 报警联动；2026-09-25 本地自测。
 * AO 保留 12 位原始量与 8 点均值；热敏温度按标称参数估算，百分比仅用于联调。
 */
#include "demo.h"
#include "./SYSTEM/delay/delay.h"
#include "./SYSTEM/usart/usart.h"
#include "./BSP/ATK_OLED/atk_oled.h"
#include "./BSP/ATK_MB026/atk_mb026.h"
#include "stm32f1xx_hal.h"
#include "kitchen_wifi.h"
#include "sample_spool.h"
#include "./BSP/ATK_MB026/atk_mb026_uart.h"
#include "oled_dashboard.h"
#include "hardware_status.h"
#include "sensor_processing.h"
#include "test_config.h"
#include "response_policy.h"
#include "hardware_control.h"
#include <stdio.h>
#include <string.h>

/* 日志对应：2026-09-21。各通道按项目接线分配；PA2/PA3 留给 OLED，PB0 接蜂鸣器。 */
#define SMOKE_AO_CHANNEL ADC_CHANNEL_0
#define TEMP_AO_CHANNEL  ADC_CHANNEL_1
#define GAS_AO_CHANNEL   ADC_CHANNEL_5
#define FLAME_AO_CHANNEL ADC_CHANNEL_7
#define SMOKE_DO_PORT GPIOB
#define SMOKE_DO_PIN  GPIO_PIN_5
#define FLAME_DO_PORT GPIOB
#define FLAME_DO_PIN  GPIO_PIN_1
#define BUZZER_PORT   GPIOB
#define BUZZER_PIN    GPIO_PIN_0
#define RELAY_PORT    GPIOB
#define RELAY_PIN     GPIO_PIN_12
#define FAN_F_PORT    GPIOA
#define FAN_F_PIN     GPIO_PIN_8
#define FAN_B_PORT    GPIOB
#define FAN_B_PIN     GPIO_PIN_13

static ADC_HandleTypeDef hadc1;
static TIM_HandleTypeDef htim3;
static uint32_t sequence;
static uint32_t adc_errors;
static SensorFilter sensor_filter;
static uint16_t filtered[SENSOR_CHANNELS];
static int32_t temperature_centi;
static uint32_t display_updates;
static ResponseOutputs response_outputs = {1u, 0u, 0u, 0u};
volatile HardwareTestStatus g_hardware_status = {HARDWARE_STATUS_MAGIC, 6u};
volatile HardwareControl g_hardware_control = {HARDWARE_CONTROL_MAGIC, 2u};
/* 编写/修改日期（日志对应）：2026-10-15。通信始终工作，采样必须授权开启。 */
static uint32_t silence_until, test_until, test_action;
static uint32_t monitoring_enabled, sample_count, arming, injection_until, injection;
static uint32_t last_publish_ms; /* 2026-10-15：网络五百毫秒上报，显示和保护独立加快。 */
static uint8_t real_hazards;
static uint32_t local_gas_threshold = KITCHEN_GAS_ALARM_THRESHOLD;
static uint32_t local_smoke_threshold = KITCHEN_SMOKE_ALARM_THRESHOLD;
static uint32_t local_temp_threshold = KITCHEN_TEMP_ALARM_CENTI;

/* 功能：应用信箱中完整提交且范围有效的平台阈值，失联继续使用最后有效值，上电有编译默认值。
 * 输入/输出：无参数；更新本地阈值和已应用修订号。联动：网关取平台规则，MCU 二次校验后独立保护。
 * 编写/修改日期（日志对应）：2026-10-02。 */
static void control_apply_rules(void)
{
    uint32_t revision = g_hardware_control.rule_revision;
    uint32_t gas = g_hardware_control.gas_threshold;
    uint32_t smoke = g_hardware_control.smoke_threshold;
    uint32_t temp = g_hardware_control.temperature_centi;
    if (!revision || revision == g_hardware_control.applied_revision) return;
    __DMB();
    if (revision != g_hardware_control.rule_revision) return;
    if (gas < 10u || gas > 95u || smoke < 10u || smoke > 95u || temp < 3500u || temp > 12000u) {
        g_hardware_control.rule_result = 2u; return;
    }
    local_gas_threshold = gas; local_smoke_threshold = smoke; local_temp_threshold = temp;
    g_hardware_control.rule_result = 1u;
    __DMB();
    g_hardware_control.applied_revision = revision;
}

/* 功能：在 HAL 单调时钟上计算限时动作余量，使用有符号差值兼容计数回绕。
 * 输入/输出：deadline 是截止毫秒；返回剩余毫秒或零。联动：消音、测试和状态上报。
 * 编写/修改日期（日志对应）：2026-10-02。 */
static uint32_t remaining_ms(uint32_t deadline)
{
    if (!deadline) return 0u;
    int32_t delta = (int32_t)(deadline - HAL_GetTick());
    return delta > 0 ? (uint32_t)delta : 0u;
}

/* 功能：读取已完整提交的命令，执行幂等关阀、限时消音、自测或三秒低压测试，并提交回执。
 * 输入/输出：hazards 为当前危险位；无返回值；回执写完后才更新 ack_sequence。
 * 模块联动：gateway.swd 写信箱，outputs_apply 执行目标。火灾拒绝消音，任何险情拒绝并中止执行器测试。
 * 编写/修改日期（日志对应）：2026-10-02、2026-10-09。 */
static void control_process(uint8_t hazards)
{
    uint32_t request = g_hardware_control.request_sequence;
    uint32_t action = g_hardware_control.action;
    uint32_t result = 1u;
    if (hazards) { test_until = 0u; test_action = 0u; }
    if (hazards & RESPONSE_FIRE) silence_until = 0u;
    if (!request || request == g_hardware_control.ack_sequence) return;
    __DMB();
    if (request != g_hardware_control.request_sequence) return;
    /* 日志对应：2026-10-15。启用先建立八点基线；停止不允许绕过仍在持续的真实险情。 */
    if (action == CONTROL_START) {
        if (real_hazards) result = 2u;
        else { monitoring_enabled = 1u; arming = 1u; memset(&sensor_filter, 0, sizeof(sensor_filter)); }
    } else if (action == CONTROL_STOP) {
        if (real_hazards) result = 2u;
        else { monitoring_enabled = 0u; arming = 0u; injection = 0u; injection_until = 0u;
               response_outputs.valve_closed = 1u; silence_until = test_until = 0u; }
    } else if (action == CONTROL_OPEN_VALVE) {
        if (!monitoring_enabled || hazards || real_hazards || sensor_filter.count < 8u || adc_errors || temperature_centi == SENSOR_TEMP_INVALID) result = 2u;
        else { response_outputs.valve_closed = 0u; arming = 0u; }
    } else if (action >= CONTROL_INJECT_GAS && action <= CONTROL_INJECT_MULTIPLE) {
        if (!monitoring_enabled || real_hazards || arming || adc_errors || temperature_centi == SENSOR_TEMP_INVALID) result = 2u;
        else { injection = action - CONTROL_INJECT_GAS + 1u; injection_until = HAL_GetTick() + 15000u; }
    } else if (action == CONTROL_CANCEL_INJECTION) { injection = 0u; injection_until = 0u; }
    else if (action == CONTROL_CLOSE_VALVE) response_outputs.valve_closed = 1u;
    else if (action == CONTROL_SILENCE) {
        if (hazards & RESPONSE_FIRE) result = 2u;
        else silence_until = HAL_GetTick() + 15000u;
    } else if (action == CONTROL_SELF_TEST) {
        g_hardware_status.processing_test_failures = sensor_processing_self_test() | (response_policy_self_test() << 8) | (kitchen_wifi_self_test() << 16);
        if (g_hardware_status.processing_test_failures || adc_errors) result = 4u;
    } else if (action >= CONTROL_TEST_BUZZER && action <= CONTROL_TEST_SERVO) {
        if (hazards || adc_errors || (action == CONTROL_TEST_SERVO && !monitoring_enabled)) result = 2u;
        else {
            test_action = action; test_until = HAL_GetTick() + 3000u;
            /* 舵机测试只验证关阀输出，既有保护锁定不得被测试解除。 */
            if (action == CONTROL_TEST_SERVO) response_outputs.valve_closed = 1u;
        }
    } else result = 3u;
    g_hardware_control.result = result;
    __DMB();
    g_hardware_control.ack_sequence = request;
}

/* 日志对应：2026-09-24。区分模拟输入、低有效数字输入和推挽输出，上电先关闭输出。 */
/* 功能：按项目分配初始化 ADC 引脚、低有效 DO 与推挽保护输出，上电先复位测试输出。
 * 输入/输出：无返回值；PB0 蜂鸣器、PB12 继电器、PA8/PB13 风扇，PA2/PA3 留给 OLED。
 * 模块联动：HAL_GPIO 和 RCC；由 demo_run 调用，避免参考 LED/KEY 抢用采集引脚。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
static void hardware_gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_ADC1_CLK_ENABLE();
    __HAL_RCC_ADC_CONFIG(RCC_ADCPCLK2_DIV6);
    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_5 | GPIO_PIN_7;
    gpio.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &gpio);
    gpio.Pin = (KITCHEN_SMOKE_SENSOR_ENABLED ? SMOKE_DO_PIN : 0u) | FLAME_DO_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &gpio);
    gpio.Pin = BUZZER_PIN | RELAY_PIN | FAN_B_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &gpio);
    gpio.Pin = FAN_F_PIN;
    HAL_GPIO_Init(GPIOA, &gpio);
    HAL_GPIO_WritePin(BUZZER_PORT, BUZZER_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(RELAY_PORT, RELAY_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(FAN_F_PORT, FAN_F_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(FAN_B_PORT, FAN_B_PIN, GPIO_PIN_RESET);
}

/* 日志对应：2026-09-21。ADC1 逐通道软件触发，启动时执行芯片 ADC 自校准。 */
/* 功能：初始化 ADC1 单次软件触发采集并执行芯片 ADC 校准，设置通道转换公共参数。
 * 输入/输出：无参数和返回值；具体通道由 adc_read 每次选择。
 * 模块联动：STM32 HAL ADC、RCC 分频，结果进入 sensor_processing。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
static void adc_init(void)
{
    hadc1.Instance = ADC1;
    hadc1.Init.ScanConvMode = ADC_SCAN_DISABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = 1;
    HAL_ADC_Init(&hadc1);
    HAL_ADCEx_Calibration_Start(&hadc1);
}

/* 日志对应：2026-09-26。转换限时 20 ms；失败累计计数供电脑诊断，避免永久等待。 */
/* 功能：按传入通道进行一次 ADC 转换，并限制等待时间，避免采样循环永久阻塞。
 * 输入/输出：channel 为 HAL ADC 通道；返回 12 位原始值。失败返回 0 并累计 adc_errors，不能据此认定有效零值。
 * 模块联动：HAL_ADC → demo_run；错误计数进入 hardware_status 和网关质量判断。
 * 编写/修改日期（日志对应）：2026-09-26。
 */
static uint16_t adc_read(uint32_t channel)
{
    ADC_ChannelConfTypeDef config = {0};
    config.Channel = channel;
    config.Rank = ADC_REGULAR_RANK_1;
    config.SamplingTime = ADC_SAMPLETIME_239CYCLES_5;
    if (HAL_ADC_ConfigChannel(&hadc1, &config) != HAL_OK) { adc_errors++; return 0; }
    if (HAL_ADC_Start(&hadc1) != HAL_OK) { adc_errors++; return 0; }
    if (HAL_ADC_PollForConversion(&hadc1, 20) != HAL_OK) { adc_errors++; return 0; }
    return (uint16_t)HAL_ADC_GetValue(&hadc1);
}

/* 日志对应：2026-09-24。72 MHz 定时器分频为 1 MHz，20 ms 周期驱动 PA6 舵机。 */
/* 功能：使用 TIM3_CH1 为 PA6 配置舵机 PWM，72 MHz 分频为 1 MHz，周期设为 20 ms。
 * 输入/输出：无参数；初始比较值为 1500 μs，初始化不提供实际舵机位置反馈。
 * 模块联动：HAL_TIM_PWM、GPIO 复用推挽；outputs_apply 后续更新比较值。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
static void servo_init(void)
{
    GPIO_InitTypeDef gpio = {0};
    TIM_OC_InitTypeDef pwm = {0};
    __HAL_RCC_TIM3_CLK_ENABLE();
    gpio.Pin = GPIO_PIN_6;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &gpio);
    htim3.Instance = TIM3;
    htim3.Init.Prescaler = 71;
    htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim3.Init.Period = 19999;
    htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_PWM_Init(&htim3);
    pwm.OCMode = TIM_OCMODE_PWM1;
    pwm.Pulse = 500; /* 2026-10-15：上电待机先关阀，授权启用且基线通过后开阀。 */
    pwm.OCPolarity = TIM_OCPOLARITY_HIGH;
    pwm.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim3, &pwm, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);
}

/* 日志对应：2026-09-24。将 0–180 度映射为 500–2500 us；舵机仅模拟阀门动作。 */
/* 功能：将调用方约定的 0～180 度映射为 500～2500 μs 比较值，作为模拟阀门指令。
 * 输入/输出：angle 是目标角度；无返回值，当前保护调用只使用 0 度或 90 度。
 * 模块联动：TIM3 CCR1 → PA6；写比较值不证明舵机已实际转动。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
static void servo_set_angle(uint8_t angle)
{
    __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1,
                          500u + ((uint32_t)angle * 2000u) / 180u);
}

/* 日志对应：2026-09-21。ADC 量程映射到 0–100 相对指标，并非气体浓度。 */
/* 功能：把 12 位 ADC 值换算为四舍五入的 0～100 相对指标，供本地阈值与显示使用。
 * 输入/输出：输入 ADC 原始值或均值，返回相对指标；不能当成 ppm 或 %LEL。
 * 模块联动：demo_run 的滤波值 → 报警判断、OLED 和遥测。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
static uint8_t percent(uint16_t value)
{
    return (uint8_t)(((uint32_t)value * 100u + 2047u) / 4095u);
}

/* 日志对应：2026-09-24。按危险类型执行保护，保留自动响应，阀门不随信号回落重新打开。 */
/* 功能：先调用统一保护策略，再将关阀、蜂鸣器、低压继电器和风扇目标写入实际外设。
 * 输入/输出：hazards 是燃气/火灾位掩码；无返回值，信号恢复不会自动解除本次关阀锁定。
 * 模块联动：response_update → HAL_GPIO 与 servo_set_angle；PC 确认报警不调用此函数重开阀。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
static void outputs_apply(uint8_t hazards)
{
    response_update(&response_outputs, hazards, KITCHEN_GAS_FAN_DEMO_ENABLED);
    control_process(hazards);
    if (!monitoring_enabled || arming) response_outputs.valve_closed = 1u;
    /* 2026-10-15：采样错误或温度换算失效也关闭阀门，不能因尚无火灾位继续供给。 */
    if (monitoring_enabled && (adc_errors || temperature_centi == SENSOR_TEMP_INVALID || g_hardware_status.processing_test_failures)) {
        response_outputs.valve_closed = 1u; response_outputs.buzzer_on = 1u;
        response_outputs.relay_active = 1u; response_outputs.fan_on = 0u; arming = 0u;
    }
    if (remaining_ms(silence_until) && !(hazards & RESPONSE_FIRE)) response_outputs.buzzer_on = 0u;
    if (!hazards && remaining_ms(test_until)) {
        if (test_action == CONTROL_TEST_BUZZER) response_outputs.buzzer_on = 1u;
        if (test_action == CONTROL_TEST_FAN) response_outputs.fan_on = 1u;
        if (test_action == CONTROL_TEST_RELAY) response_outputs.relay_active = 1u;
    }
    HAL_GPIO_WritePin(BUZZER_PORT, BUZZER_PIN, response_outputs.buzzer_on ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(RELAY_PORT, RELAY_PIN, response_outputs.relay_active ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(FAN_F_PORT, FAN_F_PIN, response_outputs.fan_on ? GPIO_PIN_SET : GPIO_PIN_RESET);
    HAL_GPIO_WritePin(FAN_B_PORT, FAN_B_PIN, GPIO_PIN_RESET);
    servo_set_angle(response_outputs.valve_closed ? 0 : 90);
}

/* 日志对应：2026-09-22。百分之一摄氏度格式化为十进制文本，负温保留符号，无效输出 null。 */
/* 功能：将百分之一摄氏度整数格式化为带符号文本，无效温度写为 null。
 * 输入/输出：buffer 和 size 为调用方缓冲区；不依赖浮点 printf，不改变温度估算。
 * 模块联动：sensor_processing 的换算结果 → OLED 与遥测 JSON。
 * 编写/修改日期（日志对应）：2026-09-22。
 */
static void temperature_text(char *buffer, uint16_t size)
{
    int32_t value = temperature_centi;
    if (value == SENSOR_TEMP_INVALID) {
        snprintf(buffer, size, "null");
    } else {
        uint32_t magnitude = (uint32_t)(value < 0 ? -value : value);
        snprintf(buffer, size, "%s%lu.%02lu", value < 0 ? "-" : "",
                 (unsigned long)(magnitude / 100u), (unsigned long)(magnitude % 100u));
    }
}

/* 日志对应：2026-09-21。每次采集更新 SWD 状态块，再发送同一组串口 JSON。
 * 无 RTC 时由网关补齐时间；温度尚未实物标定，valid 保持 false。 */
/* 功能：判定当前危险类型并执行保护、刷新 OLED，使用奇偶更新计数发布一致快照，再构造遥测。
 * 输入/输出：输入本轮 ADC、滤波结果对应指标、DO 和网络状态；串口每轮输出 JSON，网络就绪时同步透传。
 * 模块联动：response_policy、OLED、hardware_status、USART1 和 MB026；valid 保留未标定状态，控制报告不等于物理动作。
 * 编写/修改日期（日志对应）：2026-09-30。
 */
static void send_telemetry(uint8_t gas, uint8_t smoke, uint16_t smoke_raw, uint16_t temp_raw,
                           uint8_t flame, uint8_t smoke_do, uint8_t flame_do,
                           uint16_t gas_raw, uint16_t flame_raw, uint8_t net_ready)
{
    static char packet[2200];
    char temp[16];
    char smoke_text[8], smoke_raw_text[8], smoke_filtered_text[8];
    const char *smoke_do_text;
    int length;
    uint8_t hazards;
    uint8_t alarm;
    const char *alarm_name;
    control_apply_rules();
    hazards = gas >= local_gas_threshold ? RESPONSE_GAS : 0u;
    if ((KITCHEN_SMOKE_SENSOR_ENABLED && smoke >= local_smoke_threshold) || flame || flame_do ||
        (temperature_centi != SENSOR_TEMP_INVALID && temperature_centi >= (int32_t)local_temp_threshold)) hazards |= RESPONSE_FIRE;
    real_hazards = monitoring_enabled ? hazards : 0u;
    if (!remaining_ms(injection_until) || real_hazards || adc_errors || temperature_centi == SENSOR_TEMP_INVALID) { injection = 0u; injection_until = 0u; }
    /* 日期：2026-10-15。演练只替换有效判定输入，真实 ADC 与滤波数组仍原样上报。 */
    if (injection == 1u || injection == 5u) { gas = (uint8_t)(local_gas_threshold + 5u); hazards |= RESPONSE_GAS; }
    if (injection == 2u) { smoke = (uint8_t)(local_smoke_threshold + 5u); hazards |= RESPONSE_FIRE; }
    if (injection == 3u) { temperature_centi = (int32_t)local_temp_threshold + 500; hazards |= RESPONSE_FIRE; }
    if (injection == 4u || injection == 5u) { flame = 1u; hazards |= RESPONSE_FIRE; }
    if (!monitoring_enabled) { hazards = 0u; flame = 0u; }
    /* 开启后的基线检查仅允许第一次正常开阀；险情关闭锁定后必须独立操作“恢复运行”。 */
    if (arming && sensor_filter.count >= 8u) {
        if (!hazards && !adc_errors) response_outputs.valve_closed = 0u;
        arming = 0u;
    }
    alarm = hazards ? 1u : 0u;
    alarm_name = hazards == (RESPONSE_GAS | RESPONSE_FIRE) ? "multiple" :
                 (hazards & RESPONSE_FIRE) ? "fire" : (hazards & RESPONSE_GAS) ? "gas" : (monitoring_enabled && (adc_errors || temperature_centi == SENSOR_TEMP_INVALID)) ? "sensor_fault" : "normal";
    outputs_apply(hazards);
    oled_dashboard(gas,smoke,temperature_centi,flame,monitoring_enabled,arming,hazards,
                   response_outputs.valve_closed,response_outputs.fan_on,response_outputs.buzzer_on,
                   response_outputs.relay_active,net_ready,injection,sequence,HAL_GetTick());
    display_updates++;
    temperature_text(temp, sizeof(temp));
    /* 日志对应：2026-09-26。未接入通道输出 null，不能用零值伪装正常。 */
    if (KITCHEN_SMOKE_SENSOR_ENABLED) {
        snprintf(smoke_text, sizeof(smoke_text), "%u", smoke);
        snprintf(smoke_raw_text, sizeof(smoke_raw_text), "%u", smoke_raw);
        snprintf(smoke_filtered_text, sizeof(smoke_filtered_text), "%u", filtered[0]);
        smoke_do_text = smoke_do ? "1" : "0";
    } else {
        snprintf(smoke_text, sizeof(smoke_text), "null");
        snprintf(smoke_raw_text, sizeof(smoke_raw_text), "null");
        snprintf(smoke_filtered_text, sizeof(smoke_filtered_text), "null");
        smoke_do_text = "null";
    }
    /* 日志对应：2026-09-26。更新计数为奇数表示正在写入；读端只接受前后计数一致的偶数。 */
    g_hardware_status.update_count++;
    g_hardware_status.sequence = sequence++;
    g_hardware_status.uptime_ms = HAL_GetTick();
    g_hardware_status.clock_hz = SystemCoreClock;
    g_hardware_status.smoke_raw = smoke_raw;
    g_hardware_status.temp_raw = temp_raw;
    g_hardware_status.gas_raw = gas_raw;
    g_hardware_status.flame_raw = flame_raw;
    g_hardware_status.smoke_do = smoke_do;
    g_hardware_status.flame_do = flame_do;
    g_hardware_status.alarm = alarm;
    g_hardware_status.servo_pulse_us = TIM3->CCR1;
    g_hardware_status.gpio_a_output = GPIOA->ODR;
    g_hardware_status.gpio_b_output = GPIOB->ODR;
    g_hardware_status.adc_error_count = adc_errors;
    g_hardware_status.network_ready = net_ready;
    g_hardware_status.filtered_smoke_raw = filtered[0];
    g_hardware_status.filtered_temp_raw = filtered[1];
    g_hardware_status.filtered_gas_raw = filtered[2];
    g_hardware_status.filtered_flame_raw = filtered[3];
    g_hardware_status.temperature_centi_c = sensor_temperature_centi(filtered[1]);
    g_hardware_status.temperature_valid = temperature_centi != SENSOR_TEMP_INVALID;
    g_hardware_status.flame_detected = flame;
    g_hardware_status.filter_count = sensor_filter.count;
    g_hardware_status.display_update_count = display_updates;
    g_hardware_status.smoke_enabled = KITCHEN_SMOKE_SENSOR_ENABLED;
    g_hardware_status.hazard_flags = hazards;
    g_hardware_status.valve_latched = response_outputs.valve_closed;
    g_hardware_status.gas_fan_demo_enabled = KITCHEN_GAS_FAN_DEMO_ENABLED;
    g_hardware_status.control_capabilities = 65535u;
    g_hardware_status.command_sequence = g_hardware_control.ack_sequence;
    g_hardware_status.command_result = g_hardware_control.result;
    g_hardware_status.silence_remaining_ms = remaining_ms(silence_until);
    g_hardware_status.test_remaining_ms = remaining_ms(test_until);
    g_hardware_status.rules_revision = g_hardware_control.applied_revision;
    g_hardware_status.gas_threshold = local_gas_threshold;
    g_hardware_status.smoke_threshold = local_smoke_threshold;
    g_hardware_status.temperature_threshold_centi = local_temp_threshold;
    g_hardware_status.monitoring_enabled = monitoring_enabled;
    g_hardware_status.sample_count = sample_count;
    g_hardware_status.test_scenario = injection;
    g_hardware_status.injection_remaining_ms = remaining_ms(injection_until);
    g_hardware_status.effective_gas = gas; g_hardware_status.effective_smoke = smoke;
    g_hardware_status.effective_temperature_centi = temperature_centi;
    g_hardware_status.effective_flame = flame;
    g_hardware_status.wifi_state = g_wifi_config.state;
    g_hardware_status.arming = arming;
    g_hardware_status.cache_pending = sample_spool_pending();
    g_hardware_status.cache_capacity = sample_spool_capacity();
    g_hardware_status.cache_dropped = sample_spool_dropped();
    g_hardware_status.boot_identity = sample_spool_boot();
    g_hardware_status.update_count++;
    /* 2026-10-15：每轮先完成保护和显示，串口/无线仅每 500 ms 发送，减少通信阻塞。 */
    if (HAL_GetTick() - last_publish_ms < 500u) return;
    last_publish_ms = HAL_GetTick();
    sample_spool_capture();
    length = snprintf(packet, sizeof(packet),
             "{\"type\":\"telemetry\",\"boot_id\":\"mcu-%lu\",\"sampled_unix\":%lu,\"device_uptime_ms\":%lu,"
             "\"sequence\":%lu,\"sampled_at\":\"1970-01-01T00:00:00Z\","
             "\"gas\":%u,\"smoke\":%s,\"temperature\":%s,\"flame\":%s,"
             "\"valid\":false,\"io_valid\":%s,\"local_alarm\":\"%s\","
             "\"actuators\":{\"valve\":\"%s\",\"fan\":\"%s\","
             "\"power\":\"%s\",\"buzzer\":\"%s\"},"
             "\"raw\":{\"smoke_ao\":%s,\"smoke_do\":%s,\"temp_ao\":%u,"
             "\"gas_ao\":%u,\"flame_ao\":%u,\"flame_do\":%u},"
             "\"filtered\":{\"smoke_ao\":%s,\"temp_ao\":%u,\"gas_ao\":%u,\"flame_ao\":%u},"
             "\"disabled_sensors\":%s,\"firmware\":\"stm32f103-hwtest/6.0\","
             "\"monitoring_enabled\":%s,\"test_scenario\":\"%s\","
             "\"control_capabilities\":[\"close_valve\",\"silence\",\"self_test\",\"test_buzzer\",\"test_fan\",\"test_relay\",\"test_servo\",\"start_monitoring\",\"stop_monitoring\",\"open_valve\",\"inject_gas\",\"inject_smoke\",\"inject_temperature\",\"inject_flame\",\"inject_multiple\",\"cancel_injection\"],"
             "\"diagnostics\":{\"command_sequence\":%lu,\"command_result\":%lu,\"sample_count\":%lu,\"network_ready\":%u,\"wifi_state\":%lu,\"arming\":%lu,\"injection_remaining_ms\":%lu,\"rules_revision\":%lu,\"gas_fan_demo_enabled\":1,\"adc_error_count\":%lu,\"processing_test_failures\":%lu,\"silence_remaining_ms\":%lu,\"test_remaining_ms\":%lu,\"gas_threshold\":%lu,\"smoke_threshold\":%lu,\"temperature_threshold_centi\":%lu,\"cache_pending\":%lu,\"cache_capacity\":%lu,\"cache_dropped\":%lu,\"wifi_rx_overruns\":%lu}}\r\n",
             (unsigned long)sample_spool_boot(), (unsigned long)sample_spool_epoch(), (unsigned long)HAL_GetTick(),
             (unsigned long)g_hardware_status.sequence, gas, smoke_text, temp,
             (flame || flame_do) ? "true" : "false", adc_errors ? "false" : "true", alarm_name,
             response_outputs.valve_closed ? "closed" : "open", response_outputs.fan_on ? "on" : "off", response_outputs.relay_active ? "on" : "off",
             response_outputs.buzzer_on ? "on" : "off", smoke_raw_text,
             smoke_do_text, temp_raw, gas_raw, flame_raw, flame_do,
             smoke_filtered_text, filtered[1], filtered[2], filtered[3],
             KITCHEN_SMOKE_SENSOR_ENABLED ? "[]" : "[\"smoke\"]",
             monitoring_enabled ? "true" : "false",
             injection == 1u ? "gas" : injection == 2u ? "smoke" : injection == 3u ? "temperature" : injection == 4u ? "flame" : injection == 5u ? "multiple" : "",
             (unsigned long)g_hardware_control.ack_sequence, (unsigned long)g_hardware_control.result,
             (unsigned long)sample_count, net_ready, (unsigned long)g_wifi_config.state, (unsigned long)arming,
             (unsigned long)remaining_ms(injection_until), (unsigned long)g_hardware_control.applied_revision,
             (unsigned long)adc_errors, (unsigned long)g_hardware_status.processing_test_failures,
             (unsigned long)remaining_ms(silence_until), (unsigned long)remaining_ms(test_until),
             (unsigned long)local_gas_threshold, (unsigned long)local_smoke_threshold, (unsigned long)local_temp_threshold,
             (unsigned long)sample_spool_pending(), (unsigned long)sample_spool_capacity(), (unsigned long)sample_spool_dropped(),
             (unsigned long)atk_mb026_uart_stream_overruns());
    if ((length > 0) && (length < (int)sizeof(packet))) {
        printf("%s", packet);
        kitchen_wifi_send(packet, (uint16_t)length);
    }
}

/* 日志对应：2026-09-25。先初始化采集和输出，再进入每秒一次的独立运行循环。 */
/* 功能：执行不操作外设的算法自测，初始化采集与输出，按配置连接无线，然后持续采集、计算和上报。
 * 输入/输出：无参数；主循环持续运行。Wi-Fi 未配置时仍保留本地采样和报警。
 * 模块联动：main → ADC/DO → sensor_processing → 保护/OLED/SWD/串口；网络故障不阻止本地循环。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
void demo_run(void)
{
    /* 日志对应：2026-10-15。先点亮待机界面，再进行ADC校准和网络初始化，不等待Wi-Fi。 */
    atk_oled_init();
    oled_dashboard(0u,0u,SENSOR_TEMP_INVALID,0u,0u,0u,0u,1u,0u,0u,0u,0u,0u,0u,HAL_GetTick());
    /* 日志对应：2026-09-25。自测只计算已知向量，不额外操作执行器。 */
    g_hardware_status.processing_test_failures = sensor_processing_self_test() | (response_policy_self_test() << 8) | (kitchen_wifi_self_test() << 16);
    hardware_gpio_init();
    sample_spool_init();
    adc_init();
    servo_init();

    while (1) {
        /* 日期：2026-10-15。启用命令先处理，待机不触发 ADC；序号只表示通信心跳。 */
        uint32_t cycle_started = HAL_GetTick();
        kitchen_wifi_step();
        control_apply_rules();
        control_process(real_hazards);
        uint16_t smoke_raw = KITCHEN_SMOKE_SENSOR_ENABLED ? (monitoring_enabled ? adc_read(SMOKE_AO_CHANNEL) : 0u) : 0u;
        uint16_t temp_raw = (monitoring_enabled ? adc_read(TEMP_AO_CHANNEL) : 0u);
        uint16_t gas_raw = (monitoring_enabled ? adc_read(GAS_AO_CHANNEL) : 0u);
        uint16_t flame_raw = (monitoring_enabled ? adc_read(FLAME_AO_CHANNEL) : 0u);
        /* 日志对应：2026-09-21。DO 暂按低电平触发解释，须在模块标定时核对极性。 */
        uint8_t smoke_do = KITCHEN_SMOKE_SENSOR_ENABLED ?
                           (HAL_GPIO_ReadPin(SMOKE_DO_PORT, SMOKE_DO_PIN) == GPIO_PIN_RESET) : 0u;
        uint8_t flame_do = HAL_GPIO_ReadPin(FLAME_DO_PORT, FLAME_DO_PIN) == GPIO_PIN_RESET;
        uint16_t inputs[SENSOR_CHANNELS];
        uint8_t flame;
        inputs[0] = smoke_raw; inputs[1] = temp_raw; inputs[2] = gas_raw; inputs[3] = flame_raw;
        if (monitoring_enabled) { sensor_filter_push(&sensor_filter, inputs, filtered); sample_count++; }
        temperature_centi = sensor_temperature_centi(filtered[1]);
        flame = sensor_flame_detected(filtered[3], flame_do);
        send_telemetry(percent(filtered[2]), percent(filtered[0]), smoke_raw, temp_raw,
                       flame, smoke_do, flame_do, gas_raw, flame_raw, g_wifi_config.state == 5u);
        sample_spool_step(); /* 2026-10-15：本轮保护完成后才补传，不用旧样本覆盖当前输出。 */
        /* 日志对应：2026-10-13。缩短采样间隔，八点滤波仍用于抑制噪声；DO 不等待均值窗口。 */
        /* 目标 100 ms 主循环；转换、屏幕和串口耗时计入周期，实测刷新率在 OLED 显示。 */
        uint32_t cycle_elapsed = HAL_GetTick() - cycle_started;
        if (cycle_elapsed < 100u) delay_ms((uint16_t)(100u - cycle_elapsed));
    }
}

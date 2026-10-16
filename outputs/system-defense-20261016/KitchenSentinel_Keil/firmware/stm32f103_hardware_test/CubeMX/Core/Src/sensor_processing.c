/*
 * 文件职责：传感器滤波与标称参数换算。
 * 主要功能：维护四路八点均值，估算 NTC 温度，按低有效火焰方向判断，并执行已知向量自测。
 * 技术栈：C、环形缓冲、整数求和、math.h/logf、标称 NTC B=3950。
 * 模块联动：demo.c 传入原始 ADC，输出给 OLED 与状态块；自测失败位交给调试器检查，估算不代表实物校准。
 * 编写/修改日期（日志对应）：2026-09-22。
 */
/* 日志对应：2026-09-22 数据滤波与换算；2026-09-26 边界测试。
 * ATK-MB002 原厂例程采用 10k NTC、10k 上拉、B=3950、T0=298.15 K。
 * 换算依赖标称参数与相同的 3.3 V 参考；尚未与参考温度计做实物校准。
 * ATK-MB007 手册说明 AO 随火焰增强而下降，DO 为低有效。
 */
#include "sensor_processing.h"
#include <math.h>

/* 功能：用四路独立环形窗口更新累计和，减去旧值、加入新值，输出按实际点数计算的均值。
 * 输入/输出：filter 保存历史与索引，input 为四路原始值，output 接收均值；启动不足八点时不补假数据。
 * 模块联动：demo_run 每轮调用，均值交给显示、温度估算和相对指标判断。
 * 编写/修改日期（日志对应）：2026-09-22。
 */
void sensor_filter_push(SensorFilter *filter, const uint16_t input[SENSOR_CHANNELS],
                        uint16_t output[SENSOR_CHANNELS])
{
    uint8_t channel;
    if (filter->count < SENSOR_FILTER_WINDOW) filter->count++;
    for (channel = 0; channel < SENSOR_CHANNELS; channel++) {
        filter->sums[channel] -= filter->samples[channel][filter->index];
        filter->samples[channel][filter->index] = input[channel];
        filter->sums[channel] += input[channel];
        output[channel] = (uint16_t)((filter->sums[channel] + filter->count / 2u) / filter->count);
    }
    filter->index = (uint8_t)((filter->index + 1u) % SENSOR_FILTER_WINDOW);
}

/* 日志对应：2026-09-22。返回摄氏度的百分之一，避免遥测和屏幕依赖浮点 printf。
 * 端点和模块 -20~80 C 范围外的换算返回无效值，不显示虚构的温度。 */
/* 功能：按标称 10k NTC、B=3950 和 25°C 参考计算温度估算，检查端点和模块温度范围。
 * 输入/输出：adc 为均值；返回百分之一摄氏度整数，越界返回 SENSOR_TEMP_INVALID；尚未与参考温度计校准。
 * 模块联动：math.h/logf；demo.c 将结果用于显示、温度阈值与遥测，工具按带符号整数读取。
 * 编写/修改日期（日志对应）：2026-09-22。
 */
int32_t sensor_temperature_centi(uint16_t adc)
{
    float inverse_kelvin;
    float celsius;
    if (adc <= 1u || adc >= 4094u) return SENSOR_TEMP_INVALID;
    inverse_kelvin = 1.0f / 298.15f + logf((float)adc / (4096.0f - adc)) / 3950.0f;
    if (inverse_kelvin <= 0.0f) return SENSOR_TEMP_INVALID;
    celsius = 1.0f / inverse_kelvin - 273.15f;
    if (celsius < -20.0f || celsius > 80.0f) return SENSOR_TEMP_INVALID;
    return (int32_t)(celsius * 100.0f + (celsius < 0.0f ? -0.5f : 0.5f));
}

/* 日志对应：2026-09-24 报警判断。模拟阈值仍为试验值；数字触发不等待平均滤波。 */
/* 功能：按火焰 AO 随信号增强而下降的方向判断，低有效 DO 触发不等待模拟均值确认。
 * 输入/输出：adc 为滤波值，digital_active 为已转换的触发标志；返回是否检出测试火焰信号。
 * 模块联动：demo_run 采集与危险判断；模拟门限仍为试验值，需模块标定。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
uint8_t sensor_flame_detected(uint16_t adc, uint8_t digital_active)
{
    return (digital_active || adc <= 1638u) ? 1u : 0u;
}

/* 日志对应：2026-09-25 自测。直接在 MCU 上执行同一套函数，验证启动、窗口回绕、
 * 25 C 基准、量程端点和火焰极性；非零位表示失败项，供 SWD 工具阻止误报测试通过。 */
/* 功能：用固定向量核验温度基准、端点、冷热方向、火焰极性、窗口启动与回绕。
 * 输入/输出：无输入；返回失败位掩码，0 表示这些算法用例通过；不操作执行器。
 * 模块联动：demo_run 启动时执行并写 processing_test_failures，电脑工具据此核查。
 * 编写/修改日期（日志对应）：2026-09-25。
 */
uint32_t sensor_processing_self_test(void)
{
    SensorFilter filter = {0};
    uint16_t input[SENSOR_CHANNELS] = {0};
    uint16_t output[SENSOR_CHANNELS] = {0};
    uint8_t i;
    uint8_t channel;
    uint32_t failures = 0;
    int32_t reference = sensor_temperature_centi(2048u);
    if (reference < 2499 || reference > 2501) failures |= 1u;
    if (sensor_temperature_centi(0u) != SENSOR_TEMP_INVALID ||
        sensor_temperature_centi(4095u) != SENSOR_TEMP_INVALID) failures |= 2u;
    if (sensor_temperature_centi(1024u) <= reference ||
        sensor_temperature_centi(3072u) >= reference) failures |= 4u;
    if (sensor_flame_detected(4095u, 0u) || !sensor_flame_detected(1000u, 0u) ||
        !sensor_flame_detected(4095u, 1u)) failures |= 8u;
    for (i = 0; i < 16u; i++) {
        for (channel = 0; channel < SENSOR_CHANNELS; channel++) input[channel] = i;
        sensor_filter_push(&filter, input, output);
        if (i == 0u && (output[0] != 0u || filter.count != 1u)) failures |= 16u;
    }
    if (filter.count != 8u) failures |= 32u;
    for (channel = 0; channel < SENSOR_CHANNELS; channel++) {
        if (output[channel] != 12u) failures |= 64u;
    }
    return failures;
}

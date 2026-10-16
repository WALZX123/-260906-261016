/*
 * 文件职责：滤波状态结构和换算接口。
 * 主要功能：定义通道数量、窗口长度、无效温度标志、滤波状态和处理函数。
 * 技术栈：C 结构体、定宽整数、环形窗口、函数声明。
 * 模块联动：demo.c 与 sensor_processing.c 共享同一状态布局；供板上自测复用，不暴露 ADC 或显示驱动细节。
 * 编写/修改日期（日志对应）：2026-09-22。
 */
#ifndef KITCHEN_SENSOR_PROCESSING_H
#define KITCHEN_SENSOR_PROCESSING_H

#include <stdint.h>

/* 日志对应：2026-09-22 数据滤波。各路保持独立窗口，启动不足 8 点时按实际点数求均值。 */
#define SENSOR_CHANNELS 4u
#define SENSOR_FILTER_WINDOW 8u
#define SENSOR_TEMP_INVALID ((int32_t)(-2147483647 - 1))

typedef struct {
    uint16_t samples[SENSOR_CHANNELS][SENSOR_FILTER_WINDOW]; /* 各通道独立保存最近八个原始点。 */
    uint32_t sums[SENSOR_CHANNELS]; /* 窗口累计和，新增和移除采样时同步更新。 */
    uint8_t index;                  /* 下一次写入的环形位置，到窗口末尾后回绕。 */
    uint8_t count;                  /* 实际有效点数，启动时从 1 累加，最多为 8。 */
} SensorFilter;

/* 功能：用四路独立环形窗口更新累计和，减去旧值、加入新值，输出按实际点数计算的均值。
 * 输入/输出：filter 保存历史与索引，input 为四路原始值，output 接收均值；启动不足八点时不补假数据。
 * 模块联动：demo_run 每轮调用，均值交给显示、温度估算和相对指标判断。
 * 编写/修改日期（日志对应）：2026-09-22。
 */
void sensor_filter_push(SensorFilter *filter, const uint16_t input[SENSOR_CHANNELS],
                        uint16_t output[SENSOR_CHANNELS]);
/* 功能：按标称 10k NTC、B=3950 和 25°C 参考计算温度估算，检查端点和模块温度范围。
 * 输入/输出：adc 为均值；返回百分之一摄氏度整数，越界返回 SENSOR_TEMP_INVALID；尚未与参考温度计校准。
 * 模块联动：math.h/logf；demo.c 将结果用于显示、温度阈值与遥测，工具按带符号整数读取。
 * 编写/修改日期（日志对应）：2026-09-22。
 */
int32_t sensor_temperature_centi(uint16_t adc);
/* 功能：按火焰 AO 随信号增强而下降的方向判断，低有效 DO 触发不等待模拟均值确认。
 * 输入/输出：adc 为滤波值，digital_active 为已转换的触发标志；返回是否检出测试火焰信号。
 * 模块联动：demo_run 采集与危险判断；模拟门限仍为试验值，需模块标定。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
uint8_t sensor_flame_detected(uint16_t adc, uint8_t digital_active);
/* 功能：用固定向量核验温度基准、端点、冷热方向、火焰极性、窗口启动与回绕。
 * 输入/输出：无输入；返回失败位掩码，0 表示这些算法用例通过；不操作执行器。
 * 模块联动：demo_run 启动时执行并写 processing_test_failures，电脑工具据此核查。
 * 编写/修改日期（日志对应）：2026-09-25。
 */
uint32_t sensor_processing_self_test(void);

#endif

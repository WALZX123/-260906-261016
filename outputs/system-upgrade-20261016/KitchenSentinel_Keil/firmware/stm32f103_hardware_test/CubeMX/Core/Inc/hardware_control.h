/*
 * 文件职责：PC 与 STM32 之间的保护命令信箱。
 * 主要功能：约定 SWD 提交顺序、命令码和执行结果，支持关阀、限时消音、自检及短时低压执行器测试。
 * 技术栈：C、volatile RAM、32 位提交序号、定时自动恢复。
 * 模块联动：gateway.swd 先写动作再提交序号；demo 主循环执行并写回结果，采样报警始终优先。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-02、2026-10-09（执行器测试）。
 */
#ifndef KITCHEN_HARDWARE_CONTROL_H
#define KITCHEN_HARDWARE_CONTROL_H
#include <stdint.h>
#define HARDWARE_CONTROL_MAGIC 0x4348534Bu
#define CONTROL_CLOSE_VALVE 1u
#define CONTROL_SILENCE 2u
#define CONTROL_SELF_TEST 3u
#define CONTROL_TEST_BUZZER 4u
#define CONTROL_TEST_FAN 5u
#define CONTROL_TEST_RELAY 6u
#define CONTROL_TEST_SERVO 7u
/* 日志对应：2026-10-15。启停与重开阀为独立受控动作；演练仅改变判定输入，原始 ADC 保留。 */
#define CONTROL_START 8u
#define CONTROL_STOP 9u
#define CONTROL_OPEN_VALVE 10u
#define CONTROL_INJECT_GAS 11u
#define CONTROL_INJECT_SMOKE 12u
#define CONTROL_INJECT_TEMPERATURE 13u
#define CONTROL_INJECT_FLAME 14u
#define CONTROL_INJECT_MULTIPLE 15u
#define CONTROL_CANCEL_INJECTION 16u
/* 信箱字段固定为 32 位；先写 action、后写 request_sequence；ack_sequence 是最后提交的执行回执。
 * 结果 1=已执行、2=当前险情禁止测试/火灾禁止消音、3=未知命令、4=自测失败。
 * 回执只能证明软件执行，不能证明接线、供电和机械动作正确。 */
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t request_sequence;
    uint32_t action;
    uint32_t ack_sequence;
    uint32_t result;
    /* 日志对应：2026-10-02。规则先写阈值、最后提交修订号，固件再次校验范围后应用。 */
    uint32_t rule_revision;
    uint32_t gas_threshold;
    uint32_t smoke_threshold;
    uint32_t temperature_centi;
    uint32_t applied_revision;
    uint32_t rule_result; /* 1=已应用，2=范围无效保留原规则。 */
} HardwareControl;
extern volatile HardwareControl g_hardware_control;
#endif

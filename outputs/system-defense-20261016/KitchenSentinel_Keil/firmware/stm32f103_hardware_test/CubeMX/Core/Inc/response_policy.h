/*
 * 文件职责：保护策略的危险标记和接口。
 * 主要功能：定义危险位、输出状态及更新和自测接口。
 * 技术栈：C 宏、定宽整数、状态结构体。
 * 模块联动：demo.c 与 response_policy.c 共用；状态表示控制目标，不等于阀位、触点或灭火效果反馈。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
#ifndef KITCHEN_RESPONSE_POLICY_H
#define KITCHEN_RESPONSE_POLICY_H
#include <stdint.h>
/* 日志对应：2026-09-24 报警联动。自动保护保留，火灾优先抑制普通风扇，阀门保持关闭。 */
#define RESPONSE_GAS 1u   /* 危险位 0：燃气测试指标越限，可与火灾位同时出现。 */
#define RESPONSE_FIRE 2u  /* 危险位 1：火焰、烟雾或温度触发，优先禁止普通风扇。 */
typedef struct {
    uint8_t valve_closed; /* 本次运行的关阀指令锁定，信号回落不自动清零。 */
    uint8_t fan_on;       /* 仅为低压模型风扇目标，火灾时始终关闭。 */
    uint8_t buzzer_on;    /* 蜂鸣器输出目标，随当前危险变化。 */
    uint8_t relay_active; /* 低压继电器输出目标，实际触点状态需现场核验。 */
} ResponseOutputs;
/* 功能：按危险位更新保护目标：危险发生即锁定关阀，火灾禁止普通风扇，其他测试输出跟随危险。
 * 输入/输出：output 为当前输出与锁定状态，hazards 为危险类型，gas_fan_demo 仅允许低压模型演示；无返回值。
 * 模块联动：demo.outputs_apply 写 GPIO/PWM；锁定只保留在当前运行内，复位或掉电后不保留。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
void response_update(ResponseOutputs *output, uint8_t hazards, uint8_t gas_fan_demo);
/* 功能：在局部状态上检验燃气保护、火灾抑制风扇、恢复保持关阀和默认风扇关闭。
 * 输入/输出：无输入；返回失败位掩码，不初始化 GPIO，也不转动舵机。
 * 模块联动：demo_run 合并本函数与传感器自测结果，交由 SWD 工具检查。
 * 编写/修改日期（日志对应）：2026-09-25。
 */
uint32_t response_policy_self_test(void);
#endif

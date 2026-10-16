/*
 * 文件职责：本地自动保护输出策略。
 * 主要功能：按燃气或火灾危险更新关阀锁定、蜂鸣器、低压继电器和风扇演示状态。
 * 技术栈：C、危险位掩码、输出状态结构、纯函数自测。
 * 模块联动：demo.c 计算危险并调用，再把结果写 GPIO/PWM；火灾禁止普通风扇，锁定不跨复位或掉电保存。
 * 编写/修改日期（日志对应）：2026-10-16（供气演示与验收）；2026-09-24。
 */
/* 日志对应：2026-09-24 联动控制；2026-09-25 自测。
 * 自动响应只是保护动作，不能据此宣称火灾被扑灭。火灾禁止普通风扇助燃。
 * 普通风扇不用于真实燃气泄漏环境；gas_fan_demo 仅供无可燃气体的低压模型测试。
 * 阀门锁定保留到本地维护复位，PC 确认报警不能自动重新开阀。本原型锁定不跨断电保存。
 */
#include "response_policy.h"

/* 功能：按危险位更新保护目标：危险发生即锁定关阀，火灾禁止普通风扇，其他测试输出跟随危险。
 * 输入/输出：output 为当前输出与锁定状态，hazards 为危险类型，gas_fan_demo 仅允许低压模型演示；无返回值。
 * 模块联动：demo.outputs_apply 写 GPIO/PWM；锁定只保留在当前运行内，复位或掉电后不保留。
 * 编写/修改日期（日志对应）：2026-09-24。
 */
void response_update(ResponseOutputs *output, uint8_t hazards, uint8_t gas_fan_demo)
{
    if (hazards) output->valve_closed = 1u;
    output->fan_on = (gas_fan_demo && (hazards & RESPONSE_GAS) && !(hazards & (RESPONSE_FIRE | 4u))) ? 1u : 0u;
    output->buzzer_on = hazards ? 1u : 0u;
    output->relay_active = hazards ? 1u : 0u;
}

/* 功能：在局部状态上检验燃气保护、火灾抑制风扇、恢复保持关阀和默认风扇关闭。
 * 输入/输出：无输入；返回失败位掩码，不初始化 GPIO，也不转动舵机。
 * 模块联动：demo_run 合并本函数与传感器自测结果，交由 SWD 工具检查。
 * 编写/修改日期（日志对应）：2026-09-25。
 */
uint32_t response_policy_self_test(void)
{
    ResponseOutputs output = {0};
    uint32_t failures = 0;
    response_update(&output, RESPONSE_GAS, 1u);
    if (!output.valve_closed || !output.fan_on || !output.buzzer_on) failures |= 1u;
    response_update(&output, RESPONSE_GAS | RESPONSE_FIRE, 1u);
    if (output.fan_on || !output.valve_closed || !output.relay_active) failures |= 2u;
    response_update(&output, 0u, 1u);
    if (!output.valve_closed || output.fan_on || output.buzzer_on) failures |= 4u;
    response_update(&output, RESPONSE_GAS, 0u);
    if (output.fan_on || !output.valve_closed) failures |= 8u;
    return failures;
}

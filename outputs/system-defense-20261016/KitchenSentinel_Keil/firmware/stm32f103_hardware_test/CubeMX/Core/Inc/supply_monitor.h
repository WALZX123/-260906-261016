/* 文件职责：供气工况演示状态机的公共接口。
 * 功能：开阀稳定、持续低值判定和人工复位；输入为电位器相对指标，不是压力或流量。
 * 技术栈：C99、单调毫秒计数；联动：demo 调用，response_policy 执行保护，平台保存事件。
 * 编写/修改日期（日志对应）：2026-10-16。 */
#ifndef KITCHEN_SUPPLY_MONITOR_H
#define KITCHEN_SUPPLY_MONITOR_H
#include <stdint.h>
typedef struct {
    uint32_t opened_at, low_at;
    uint8_t was_open, low_pending, latched, state;
} SupplyMonitor;
/* 输入启用、采样有效、开阀、指标和规则；输出状态0禁用、1未评估、2稳定中、3评估中、4故障锁存。
 * 关阀与禁用只停止评估，不清除已发生的故障；毫秒差采用无符号运算兼容时钟回绕。 */
void supply_update(SupplyMonitor *s, uint32_t now, uint8_t enabled, uint8_t valid,
                   uint8_t open, uint8_t value, uint32_t threshold, uint32_t settle_ms, uint32_t hold_ms);
/* 仅独立授权的安全开阀操作调用；清除锁存并重新计时，不由报警确认或关闭演练调用。 */
void supply_reset(SupplyMonitor *s);
/* 不操作外设的边界向量测试；返回失败位，供 MCU 自检及主机编译复用。 */
uint32_t supply_self_test(void);
#endif

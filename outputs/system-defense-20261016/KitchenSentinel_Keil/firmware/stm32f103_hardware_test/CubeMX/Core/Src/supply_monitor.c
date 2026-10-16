/* 文件职责：独立于网络的供气工况演示判定。
 * 功能：只在有效开阀工况下等待稳定时间，再累计低值持续时间，故障保持到授权重新开阀。
 * 技术栈：C99、有限状态机、uint32_t 时钟差；联动：demo 的电位器输入与本地保护输出。
 * 编写/修改日期（日志对应）：2026-10-16。 */
#include "supply_monitor.h"
#include <string.h>

/* 保留故障锁存的优先级；任何停止评估的情况都丢弃未完成的低值计时，避免跨开阀周期拼接。 */
void supply_update(SupplyMonitor *s, uint32_t now, uint8_t enabled, uint8_t valid,
                   uint8_t open, uint8_t value, uint32_t threshold, uint32_t settle_ms, uint32_t hold_ms)
{
    if (s->latched) { s->state=4u; return; }
    if (!enabled || !valid || !open) {
        s->was_open=0u; s->low_pending=0u; s->state=enabled?1u:0u; return;
    }
    if (!s->was_open) { s->opened_at=now; s->was_open=1u; }
    if ((uint32_t)(now-s->opened_at)<settle_ms) { s->state=2u; return; }
    s->state=3u;
    if (value>=threshold) { s->low_pending=0u; return; }
    if (!s->low_pending) { s->low_at=now; s->low_pending=1u; }
    if ((uint32_t)(now-s->low_at)>=hold_ms) { s->latched=1u; s->state=4u; }
}
/* 全部清零使下一次有效开阀重新经历稳定窗口；调用方负责权限和其他险情检查。 */
void supply_reset(SupplyMonitor *s) { memset(s,0,sizeof(*s)); }
/* 验证关阀不误报、稳定期不误报、短暂低值被清除、持续低值锁存、禁用不消警和时钟回绕。 */
uint32_t supply_self_test(void)
{
    SupplyMonitor s={0}; uint32_t fail=0;
    supply_update(&s,0u,1u,1u,0u,0u,15u,100u,50u);
    if(s.latched || s.state!=1u) fail|=1u;
    supply_update(&s,10u,1u,1u,1u,0u,15u,100u,50u);
    supply_update(&s,109u,1u,1u,1u,0u,15u,100u,50u);
    if(s.latched || s.state!=2u) fail|=2u;
    supply_update(&s,110u,1u,1u,1u,0u,15u,100u,50u);
    supply_update(&s,140u,1u,1u,1u,20u,15u,100u,50u);
    supply_update(&s,160u,1u,1u,1u,0u,15u,100u,50u);
    supply_update(&s,209u,1u,1u,1u,0u,15u,100u,50u);
    if(s.latched) fail|=4u;
    supply_update(&s,210u,1u,1u,1u,0u,15u,100u,50u);
    supply_update(&s,220u,0u,0u,0u,20u,15u,100u,50u);
    if(!s.latched || s.state!=4u) fail|=8u;
    supply_reset(&s);
    supply_update(&s,0xFFFFFFF0u,1u,1u,1u,0u,15u,20u,10u);
    supply_update(&s,4u,1u,1u,1u,0u,15u,20u,10u);
    supply_update(&s,14u,1u,1u,1u,0u,15u,20u,10u);
    if(!s.latched) fail|=16u;
    return fail;
}

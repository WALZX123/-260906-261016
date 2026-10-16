/** 文件职责：供气工况演示的实时业务状态。
 * 功能：区分关闭、未评估、稳定中、评估中与故障锁存；保留环境监测的独立含义。
 * 技术栈：React、TypeScript；关联STM32诊断、设备快照和报警中心。
 * 编写/修改日期（日志对应）：2026-10-16。 */
import {Badge,Panel} from './components';
import type {Sample} from './types';
/** 只依据实际设备诊断显示已生效状态；关阀时绝不以零值或正常代替未评估。 */
export function SupplyStatus({sample,online=true}:{sample:Partial<Sample>;online?:boolean}){
 const d=sample.diagnostics||{},enabled=!!d.supply_demo_enabled,latched=!!d.supply_low_latched;
 const open=sample.actuators?.valve==='open';
 const evaluating=online&&sample.monitoring_enabled!==false&&enabled&&d.supply_state===3&&open;
 const status=!online?'设备离线 · 最后状态':latched?'供气异常锁存 · 需人工核查':!enabled?'供气演示未开启':sample.monitoring_enabled===false||!open?'未评估 · 阀门关闭':d.supply_state===2?'开阀稳定中':'等待设备工况';
 return <Panel title="供气工况演示" extra={<Badge value={latched?'active':evaluating?'normal':''}>{evaluating?'正在评估':status}</Badge>}>
  <div className="supply-state"><strong>{evaluating?`${sample.gas??'—'} / 100`:'未评估'}</strong><span>{evaluating?`低值阈值 ${d.supply_low_threshold??'—'} · 持续 ${(d.supply_hold_ms||0)/1000} 秒触发`:status}</span></div>
  <p className="muted">开阀后稳定 {(d.supply_settle_ms||5000)/1000} 秒再评估。电位器仅演示供气指标，不能确定真实压力不足或漏气；关阀后环境燃气、烟雾、温度和火焰监测继续。</p>
  {latched&&<p role="alert">已自动关阀、鸣响并转人工。结束演练、信号回升或确认报警均不会重开阀；现场核查后需独立执行“恢复运行并开阀”。</p>}
 </Panel>;
}

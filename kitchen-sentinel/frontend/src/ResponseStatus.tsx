/**
 * 文件职责：报警处置进度的统一展示。
 * 主要功能：分别显示自动响应、人工确认和人工升级，解释原因与动作反馈。
 * 技术栈：React、TypeScript、状态映射、HTML 表格。
 * 模块联动：ResponseQueue 与 Alarms 复用；数据来自 domain.response，控制输出不能当作实际阀位或灭火效果。
 * 编写/修改日期（日志对应）：2026-10-05、2026-10-13（输出语义与正式页面名称）。
 */
// 日志对应：2026-10-03。自动响应、报警确认、人工升级分别显示，恢复信号不能冒充灭火成功。
import {Badge,Notice} from './components';
import type {Alarm} from './types';

const progress:Record<string,string>={monitoring:'自动输出已反馈，观察效果',awaiting_feedback:'等待自动输出反馈',
 protection_reported:'保护输出已反馈',auto_resolved:'自动处置完成（模拟）',signal_recovered:'信号已恢复',reconnecting:'等待自动重连',connection_recovered:'连接已恢复',inspection_required:'需要人工检查',not_recorded:'历史动作未记录'};
const reasons:Record<string,string>={fire:'火灾警情超出自动处置能力',beyond_limit:'指标超过自动处置范围',
 automatic_timeout:'自动响应后异常仍持续，超过观察时限',reconnect_timeout:'自动重连观察超时，需要检查连接',execution_failed:'保护命令执行失败',inspection_required:'采样或连接异常需要检查',historical_review:'历史事件需要复核',onsite_issue:'现场观察到自动执行异常，需要人工核查'};
const descriptions:Record<string,string>={signal_recovered:'信号已恢复，报警记录保留供人工确认。',connection_recovered:'连接已恢复，报警记录保留供人工确认。',
 auto_resolved:'模拟器闭环已完成，报警记录仍待人员确认。',not_recorded:'这条历史事件没有保存自动动作反馈，不能由此判断处置效果。',reconnecting:'系统正在自动重连，超过观察时限再升级人工检查。'};
const actuatorNames:Record<string,string>={valve:'阀门控制',fan:'排风装置',buzzer:'蜂鸣器',power:'低压继电器保护输出'};
const stateNames:Record<string,string>={closed:'关闭',open:'开启',on:'开启',off:'关闭'};

/** 区分继电器控制电平和被保护电源状态，防止把“保护输出有效”误读为火灾时恢复供电。
 * 编写/修改日期（日志对应）：2026-10-13。 */
function outputState(alarm:Alarm,actuator:string,value:string){
 if(actuator==='power')return alarm.response.feedback_level==='simulated_feedback'?(value==='off'?'电源切断':'电源供电'):(value==='on'?'保护输出有效':'保护输出未触发');
 return stateNames[value]||value;
}

/** 同时显示自动响应、报警确认和人工处置三个独立状态，避免信号恢复覆盖待确认提示。
 * 编写/修改日期（日志对应）：2026-10-05。 */
export function ResponseTags({alarm}:{alarm:Alarm}){
 const response=alarm.response;
 return <div className="response-tags"><Badge value={alarm.status==='active'?'pending':'succeeded'}>{progress[response?.automatic_status||'not_recorded']}</Badge>
  <Badge value={alarm.acknowledged_at?'succeeded':'pending'}>{alarm.acknowledged_at?'报警已确认':'报警待确认'}</Badge>
  {response?.manual_required&&<Badge value="fire">需人工处置</Badge>}
  {response?.resolution&&<Badge value="succeeded">人工处置已记录</Badge>}
 </div>;
}

/** 解释人工升级原因并比对动作目标与输出报告，显示现场处置记录及反馈边界。
 * 编写/修改日期（日志对应）：2026-10-05。 */
export function ResponseDetails({alarm}:{alarm:Alarm}){
 const response=alarm.response;
 if(!response)return <Notice>这条历史事件未保存自动响应反馈。</Notice>;
 return <><ResponseTags alarm={alarm}/>
  <Notice warn={response.manual_required}>{response.manual_required?response.reasons.map(reason=>reasons[reason]||reason).join('；'):
   response.resolution?'已记录人工现场核查，设备保护状态不由本条记录改变。':
   descriptions[response.automatic_status]||'在自动响应范围内，系统继续执行保护并观察效果。'}</Notice>
  {!!response.actions.length&&<div className="table-wrap"><table><thead><tr><th>自动动作</th><th>目标状态</th><th>设备报告</th></tr></thead><tbody>{response.actions.map(action=><tr key={action.actuator}><td>{action.actuator==='power'&&response.feedback_level==='simulated_feedback'?'非消防电源':actuatorNames[action.actuator]||action.actuator}</td><td>{outputState(alarm,action.actuator,action.expected)}</td><td>{action.reported?outputState(alarm,action.actuator,action.reported):'暂无反馈'} · {action.matched?'符合目标':'待核验'}</td></tr>)}</tbody></table></div>}
  <p className="muted">{response.feedback_level==='simulated_feedback'?'反馈来自设备模拟器。':'反馈只证明控制输出，不能代替实际阀位、断电或灭火效果核验。'}</p>
  {response.resolution&&<p>人工现场核查：{response.resolution.by} · {response.resolution.note}</p>}
 </>;
}

/**
 * 文件职责：现场保护命令与执行记录。
 * 主要功能：按设备下发关阀、限时消音，展示固件能力、命令状态与回执；测试动作只在系统测试页提供。
 * 技术栈：React Hooks、TypeScript、REST、UUID 幂等键。
 * 模块联动：platform 创建命令，网关提交信箱，MCU 执行后回执；实物输出不等于机械位置反馈。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-02、2026-10-09。
 */
import {useState} from 'react';
import {post} from '../api';
import {Badge,Empty,fmt,Modal,Notice,Panel,labels} from '../components';
import type {Snapshot,User} from '../types';

/** 依据实机上报的能力开放操作，危险期间由固件再次检查测试和消音条件。
 * 编写/修改日期（日志对应）：2026-10-02、2026-10-09。 */
export function Control({data,user,refresh,notify,testing=false}:{data:Snapshot;user:User;refresh:()=>Promise<void>;notify:(s:string)=>void;testing?:boolean}){
 const [confirm,setConfirm]=useState(''),[busy,setBusy]=useState(false),[deviceId,setDeviceId]=useState('');
 const device=data.devices.find(d=>d.id===deviceId)||data.devices[0];
 const can=(action:string)=>device?.source==='simulated'?['close_valve','silence','self_test'].includes(action):device?.latest.control_capabilities?.includes(action);
 const commands=data.commands.filter(c=>c.device_id===device?.id);
 const actions=[
  ...(device?.source==='hardware'?[{action:'open_valve',title:'恢复运行并开阀',text:'确认现场无险情后解除关阀锁定；必须已开启采样且基线正常，报警记录和待确认状态保留。'}]:[]),
  {action:'close_valve',title:'紧急关阀',text:'保持关阀锁定，信号恢复和人工确认均不会自动开阀。'},
  {action:'silence',title:'暂时消音',text:'蜂鸣器暂时消音 15 秒；新火灾信号立即恢复鸣响，其他保护继续。'},
  ...(testing?[{action:'self_test',title:'固件自检',text:'运行 MCU 算法向量与 ADC 错误检查，不代替传感器标定和机械动作验收。'},
   {action:'test_buzzer',title:'蜂鸣器测试',text:'输出 3 秒，结束后自动恢复。'},
   {action:'test_fan',title:'风扇测试',text:'低压台架输出 3 秒，任何险情立即中止测试并交由自动策略处理。'},
   {action:'test_relay',title:'继电器测试',text:'低压继电器输出 3 秒，测试后恢复原策略。'},
   {action:'test_servo',title:'舵机关阀测试',text:'发送 500 μs 关阀脉宽并保持锁定；请现场观察运动，需要重复测试时，在确认无险情后使用恢复运行并开阀。'}]:[])
 ].filter(item=>device?.source!=='simulated'||!item.action.startsWith('test_'));
 /** 创建命令并刷新记录，保留服务端和 MCU 的拒绝原因，不把“创建”显示为“执行完成”。
  * 编写/修改日期（日志对应）：2026-10-02。 */
 const send=async(action:string)=>{if(!device||!can(action))return;setBusy(true);try{await post('/devices/'+device.id+'/commands',{action,idempotency_key:crypto.randomUUID()});notify('命令已下发，正在等待设备执行回执');setConfirm('');await refresh()}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 return <>
  <Panel title="控制对象"><label>设备 <select aria-label="控制设备" value={device?.id||''} onChange={e=>setDeviceId(e.target.value)}>{data.devices.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><p>固件：{device?.firmware||'尚未接入'} · {device?.online?'在线':'离线'}</p></Panel>
  {!device?.latest.control_capabilities?.length&&device?.source==='hardware'&&<Notice warn>尚未收到支持远程执行的固件能力，请检查设备连接及版本。</Notice>}
  <div className="control-grid">{actions.map(item=><section className="panel control-card" key={item.action}><h2>{item.title}</h2><p>{item.text}</p><button disabled={busy||user.role==='viewer'||!device?.online||!can(item.action)} className={'button '+(item.action==='close_valve'?'danger':'secondary')} onClick={()=>item.action==='close_valve'||item.action==='open_valve'||item.action.startsWith('test_')?setConfirm(item.action):void send(item.action)}>{item.title}</button></section>)}</div>
  <Panel title="命令与执行记录" extra={<span className="muted">自动刷新 · 最近 50 条</span>}>
  {commands.length?<div className="table-wrap"><table><thead><tr><th>命令</th><th>发起人</th><th>创建时间</th><th>状态</th><th>执行回执</th></tr></thead><tbody>{commands.map(c=><tr key={c.id}><td><strong>{labels[c.action]||actions.find(a=>a.action===c.action)?.title||c.action}</strong><small>{c.id.slice(0,8)}</small></td><td>{c.requested_by}</td><td>{fmt(c.created_at)}</td><td><Badge value={c.status}/></td><td className="wide-cell">{c.result||'等待设备执行回执'}</td></tr>)}</tbody></table></div>:<Empty text="尚无命令记录"/>}
  <div className="panel-foot">控制回执说明固件已处理指令。舵机位置、风扇运转及继电器触点需现场验收。</div></Panel>
  {confirm&&<Modal title={'确认'+(actions.find(a=>a.action===confirm)?.title||'操作')} onClose={()=>setConfirm('')}><p>设备：{device?.name}。{actions.find(a=>a.action===confirm)?.text}</p><div className="button-row"><button className="button" disabled={busy} onClick={()=>void send(confirm)}>确认执行</button><button className="button secondary" onClick={()=>setConfirm('')}>取消</button></div></Modal>}
 </>;
}

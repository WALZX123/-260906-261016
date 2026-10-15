/**
 * 文件职责：系统演练、异常流程与硬件分项验证。
 * 主要功能：顶部列出全部警报及保护策略，限时注入五种 MCU 险情，单独验证故障/离线/超时，集中查看演练报警。
 * 技术栈：React、TypeScript、REST、实时订阅；模块联动：真实控制信箱、独立模拟节点、Alarms 和 Control。
 * 编写/修改日期（日志对应）：2026-10-09、2026-10-12、2026-10-15。
 */
import {useState} from 'react';
import {useMonitor} from '../useMonitor';
import {api,post} from '../api';
import {Notice,Panel,Badge,labels} from '../components';
import {SensorReadings} from '../SensorReadings';
import {Alarms} from './Alarms';
import {Control} from './Control';
import type {Snapshot,User} from '../types';
const catalog=[
 {id:'gas',title:'燃气超限',action:'inject_gas',policy:'关阀 · 蜂鸣 · 保护继电器 · 低压排风；持续超时或超过自动范围转人工'},
 {id:'smoke',title:'烟雾报警',action:'inject_smoke',policy:'关阀 · 蜂鸣 · 保护继电器 · 关闭普通风扇 · 立即转人工'},
 {id:'temperature',title:'温度过高',action:'inject_temperature',policy:'按火灾信号处理：关阀、报警、停风扇，并要求人工处置'},
 {id:'flame',title:'火焰报警',action:'inject_flame',policy:'关阀 · 持续蜂鸣 · 保护继电器 · 停风扇 · 立即转人工'},
 {id:'multiple',title:'复合险情',action:'inject_multiple',policy:'燃气与火灾并发时采用火灾优先策略，停风扇并转人工'},
 {id:'sensor_fault',title:'采样故障',action:'',policy:'记录无效通道，提示人工检查传感器、接线与供电'},
 {id:'offline',title:'设备离线',action:'',policy:'显示最后上报时间，产生离线报警；重连后记录恢复，仍待人工确认'},
 {id:'command_timeout',title:'控制失败 / 超时',action:'',policy:'命令独立留档，升级人工核查；重试成功仍保留待确认记录'}
];
/** 按危险类型选取实时事件；五种实物演练有十五秒时限，三种软件故障使用独立节点。日期：2026-10-15。 */
export function SystemTest({hardware,user,refresh,notify}:{hardware:Snapshot;user:User;refresh:()=>Promise<void>;notify:(s:string)=>void}){
 const {snapshot:data,refresh:refreshTests,connected,error}=useMonitor(true,'simulated');
 const [section,setSection]=useState('hardware'),[busy,setBusy]=useState(false),[managed,setManaged]=useState(false);
 const simulation=data?.devices[0], device=hardware.devices.find(d=>d.source==='hardware'), readonly=user.role==='viewer';
 /** 下发带幂等键的限时演练，真实采样的险情可立即取消注入并接管保护。日期：2026-10-15。 */
 const inject=async(action:string)=>{if(!device)return;setBusy(true);try{await post('/devices/'+device.id+'/commands',{action,idempotency_key:crypto.randomUUID()});notify(action==='cancel_injection'?'已请求结束演练；记录保留，确认安全后可恢复开阀':'演练命令已提交；持续十五秒，原始读数保留');await refresh()}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 /** 托管模拟进程只供故障链路验证，等待节点真正上报后才切换场景。日期：2026-10-09、2026-10-15。 */
 const software=async(name:string)=>{setBusy(true);try{
  let node=simulation;
  if(!node?.online){await post('/testing/simulator/start');setManaged(true);for(let i=0;i<15;i++){await new Promise(r=>setTimeout(r,400));const snapshot=await api<Snapshot>('/snapshot?scope=simulated');node=snapshot.devices.find(d=>d.online);if(node)break}}
  if(!node?.online)throw new Error('模拟节点尚未上线，请稍后重试');
  await post('/devices/'+node.id+'/scenario',{scenario:name});await refreshTests();setSection('software');notify('独立故障场景已切换，测试记录与现场设备分别保存');
 }catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 /** 停止本服务托管的模拟节点；先恢复正常采样，让故障产生明确恢复记录。日期：2026-10-15。 */
 const stopSoftware=async()=>{if(!simulation)return;setBusy(true);try{await post('/devices/'+simulation.id+'/scenario',{scenario:'normal'});await new Promise(r=>setTimeout(r,6000));await post('/testing/simulator/stop');setManaged(false);notify('软件场景已停止，历史记录继续保留');await refreshTests()}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 return <>
  <Panel title="全部警报与对应策略" extra={<Badge>全部异常留档 · 恢复后仍待人工确认</Badge>}>
   <Notice>前五项直接验证已连接的低压硬件：由 MCU 注入十五秒判定信号并真实控制输出，不需要制造烟雾或使用明火。原始 ADC 保持实际读数，事件注明演练。先到“设备启用”开启采样；真实险情优先。</Notice>
   {device?.latest.test_scenario&&<Notice warn>正在演练：{catalog.find(c=>c.id===device.latest.test_scenario)?.title||device.latest.test_scenario} · 剩余 {Math.ceil((device.latest.diagnostics?.injection_remaining_ms||0)/1000)} 秒 <button className="button secondary" disabled={busy||readonly} onClick={()=>void inject('cancel_injection')}>立即结束演练</button></Notice>}
   <div className="alarm-catalog">{catalog.map(item=><section key={item.id}><div className="button-row"><strong>{item.title}</strong><Badge>{item.action?'实物联动':'独立软件场景'}</Badge></div><p>{item.policy}</p><button className="button secondary" disabled={busy||readonly||(!!item.action&&(!device?.online||!device.latest.monitoring_enabled||!!device.latest.diagnostics?.arming||!device.latest.control_capabilities?.includes(item.action)))} onClick={()=>item.action?void inject(item.action):void software(item.id)}>{item.action?'开始 15 秒演练':'验证异常流程'}</button></section>)}</div>
   <p className="muted">演练结束后保护输出按真实信号恢复，阀门保持关闭；确认现场正常后，在联动控制中“恢复运行并开阀”。</p>
  </Panel>
  <div className="test-tabs tabs">{[['hardware','硬件与执行器'],['alarms','实物演练记录'],['software','软件故障记录']].map(([id,title])=><button key={id} className={section===id?'selected':''} onClick={()=>setSection(id)}>{title}</button>)}</div>
  {section==='hardware'&&<>
   {device&&<Panel title="现场节点实时状态" extra={<Badge value={device.online?'succeeded':'offline'}>{device.latest.monitoring_enabled?'采样运行':'待机'}</Badge>}>
    <div className="diagnostic-grid">{[['传输通道',device.latest.transport==='tcp'?'Wi-Fi 双向通信':'SWD 调试器'],['阀门',labels[device.actuators.valve]||'—'],['风扇',labels[device.actuators.fan]||'—'],['蜂鸣器',labels[device.actuators.buzzer]||'—'],['保护继电器',device.actuators.power==='on'?'保护有效':'未触发'],['固件',device.firmware]].map(([name,value])=><div key={name}><span>{name}</span><b>{value}</b></div>)}</div>
    <details><summary>查看传感器原始通道与采样诊断</summary><SensorReadings sample={device.latest}/><p>ADC 错误：{device.latest.diagnostics?.adc_error_count??'未上报'} · 算法自测：{device.latest.diagnostics?.processing_test_failures===0?'通过':'等待上报'} · 实际采样轮数：{device.latest.diagnostics?.sample_count??'—'}</p></details>
   </Panel>}
   <Control data={hardware} user={user} refresh={refresh} notify={notify} testing/>
  </>}
  {section==='alarms'&&<Alarms data={hardware} user={user} refresh={refresh} notify={notify}/>}
  {section==='software'&&<><Panel title="独立软件故障验证" extra={<Badge value={simulation?.online?'succeeded':'offline'}>{connected&&simulation?.online?'模拟节点在线':'模拟节点未在线'}</Badge>}>
   <p>用于验证采样故障、离线和命令超时，不改变现场设备。执行超时场景需点击下方“固件自检”创建命令，等待超时报警。</p>
   <div className="button-row"><button className="button secondary" disabled={busy||readonly} onClick={()=>void software('normal')}>恢复软件正常场景</button><button className="button secondary" disabled={busy||readonly||!simulation?.online} onClick={()=>void software('command_timeout')}>切换命令超时</button><button className="button secondary" disabled={busy||readonly||!managed} onClick={()=>void stopSoftware()}>停止软件场景</button></div>
   {error&&<Notice warn>{error}</Notice>}
  </Panel>{data&&<><Control data={data} user={user} refresh={refreshTests} notify={notify} testing/><Alarms data={data} user={user} refresh={refreshTests} notify={notify} scope="simulated"/></>}</>}
 </>;
}


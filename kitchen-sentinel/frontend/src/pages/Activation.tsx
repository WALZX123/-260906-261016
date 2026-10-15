/** 文件职责：现场设备启用与无线连接页面。
 * 主要功能：显式开启/暂停采样、正常恢复开阀、脱敏配置 Wi-Fi，展示运行和通信状态。
 * 技术栈：React、TypeScript、REST；模块联动：设备命令、wifi 接口与实时快照。
 * 编写/修改日期（日志对应）：2026-10-02、2026-10-15。 */
import {useEffect,useState} from 'react';
import {api,post} from '../api';
import {Badge,Notice,Panel,labels} from '../components';
import type {Snapshot,User} from '../types';
type Wifi={configured:boolean;ssid:string;host:string;port:number};
/** 显示启用入口和真实回执；通信在线不等同采样运行，待机值不当作正常测量。日期：2026-10-15。 */
export function Activation({data,user,refresh,notify}:{data:Snapshot;user:User;refresh:()=>Promise<void>;notify:(s:string)=>void}){
 const device=data.devices.find(d=>d.source==='hardware');
 const [busy,setBusy]=useState(false),[wifi,setWifi]=useState<Wifi|null>(null),[ssid,setSsid]=useState(''),[password,setPassword]=useState(''),[host,setHost]=useState('');
 useEffect(()=>{void api<Wifi>('/wifi').then(v=>{setWifi(v);setSsid(v.ssid);setHost(v.host)}).catch(e=>notify(e.message))},[notify]);
 const running=device?.latest.monitoring_enabled===true, readonly=user.role==='viewer';
 const state=device?.latest.diagnostics?.wifi_state??0;
 const network=['未配置','连接中','模块无 AT 回应','热点连接失败','电脑连接失败','双向连接正常'][state]||'等待状态';
 /** 创建受审计的启停或恢复命令，执行条件由 MCU 按真实险情再次检查。日期：2026-10-15。 */
 const command=async(action:string)=>{if(!device)return;if(action==='open_valve'&&!window.confirm('确认现场已恢复正常，并恢复阀门开启？报警确认记录将继续保留。'))return;setBusy(true);try{await post('/devices/'+device.id+'/commands',{action,idempotency_key:crypto.randomUUID()});notify('已提交设备操作，等待固件回执');await refresh()}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 /** 仅待机时更新热点和电脑地址；密码提交后清空，接口只返回脱敏状态。日期：2026-10-15。 */
 const configure=async()=>{setBusy(true);try{const result=await post<Wifi>('/wifi',{ssid,password,host});setWifi(result);setPassword('');notify('无线配置已保存，正在连接手机热点');await refresh()}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 const disabled=busy||readonly||!device?.online;
 return <>
  <Panel title="设备运行开关" extra={<Badge value={running?'succeeded':'pending'}>{running?'采样运行中':'待机 · 采样未开启'}</Badge>}>
   <p>设备上电先待机。开启后检查八点采样基线，无险情才打开阀门；出现险情自动关闭，恢复后由操作人员重新开阀。</p>
   <div className="diagnostic-grid">{[['现场设备',device?.name||'等待接入'],['通信',device?.online?'在线':'离线'],['当前运行',running?(device?.latest.diagnostics?.arming?'基线检查中':'正在采样'):'待机'],['阀门输出',labels[device?.actuators.valve||'']||'等待上报'],['数据通道',device?.latest.transport==='tcp'?'Wi-Fi 无线':device?.latest.transport==='swd'?'调试器连接':'等待接入'],['实际采样轮数',device?.latest.diagnostics?.sample_count??'—']].map(([name,value])=><div key={name}><span>{name}</span><b>{value}</b></div>)}</div>
   <div className="button-row"><button className="button" disabled={disabled||running||!device?.latest.control_capabilities?.includes('start_monitoring')} onClick={()=>void command('start_monitoring')}>开启硬件采样</button><button className="button secondary" disabled={disabled||!running} onClick={()=>void command('stop_monitoring')}>暂停采样并关阀</button><button className="button secondary" disabled={disabled||!running||device?.actuators.valve==='open'} onClick={()=>void command('open_valve')}>恢复运行并开阀</button></div>
   {readonly&&<Notice>只读账号可查看运行状态，管理员和操作员可启用设备。</Notice>}
   {device?.latest.test_scenario&&<Notice warn>正在执行{labels[device.latest.test_scenario]||device.latest.test_scenario}演练，原始通道仍保留实际读数。</Notice>}
  </Panel>
  <Panel title="Wi-Fi 无线连接" extra={<Badge value={state===5?'succeeded':'pending'}>{network}</Badge>}>
   <p>MB026 负责 STM32 与电脑之间的遥测、报警、阈值及控制回执。电脑和模块连接同一个手机热点，电脑接收端口为 9000。</p>
   <div className="form-grid"><label>手机热点名称<input value={ssid} onChange={e=>setSsid(e.target.value)} disabled={readonly}/></label><label>热点密码<input type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} disabled={readonly} placeholder="更改配置时填写，不回显已存密码"/></label><label>电脑的热点 IPv4 地址<input value={host} onChange={e=>setHost(e.target.value)} disabled={readonly} placeholder="例如 192.168.43.100"/></label></div>
   <div className="button-row"><button className="button secondary" disabled={busy||readonly||running||!ssid||!host} onClick={()=>void configure()}>保存并连接热点</button><span className="muted">{wifi?.configured?'本机已保存配置；改变网络前先暂停采样':'等待设置无线连接'}</span></div>
   <p className="muted">接线：模块 TXD→PB11、RXD→PB10、RST→PA4，供电并共地。手机热点需支持 2.4 GHz，电脑地址变化后在此更新。</p>
  </Panel>
 </>;
}

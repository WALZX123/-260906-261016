// 联动控制页：创建幂等命令并观察设备回执或超时结果。
import {useState} from 'react';
import {BellOff,CheckCircle2,Power,ShieldAlert} from 'lucide-react';
import {post} from '../api';
import {Badge,Empty,fmt,Modal,Notice,Panel,labels} from '../components';
import type {Snapshot,User} from '../types';
export function Control({data,user,refresh,notify}:{data:Snapshot;user:User;refresh:()=>Promise<void>;notify:(s:string)=>void}){
 const [confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false);
 const device=data.devices[0];
 const send=async(action:string)=>{if(!device)return;setBusy(true);try{await post(`/devices/${device.id}/commands`,{action,idempotency_key:crypto.randomUUID()});notify('命令已创建，执行结果请查看下方记录');setConfirm(false);await refresh()}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 return <><Notice>命令下发与设备执行分开记录。当前操作对象是模拟设备，真实阀门尚未接入。</Notice><div className="control-grid">{[{action:'close_valve',title:'紧急关阀',text:'关闭模拟燃气阀门并等待设备确认。系统不提供远程开阀。',icon:ShieldAlert,danger:true},{action:'silence',title:'暂时消音',text:'蜂鸣器消音 15 秒。报警事件和其他保护动作继续保留。',icon:BellOff},{action:'self_test',title:'设备自检',text:'检查模拟采集与控制路径。真实硬件检测待实物接入后补充。',icon:CheckCircle2}].map(item=><section className="panel control-card" key={item.action}><div className={'control-icon '+(item.danger?'danger':'')}><item.icon size={27}/></div><h2>{item.title}</h2><p>{item.text}</p><button disabled={busy||user.role==='viewer'||!device?.online} className={'button '+(item.danger?'danger':'secondary')} onClick={()=>item.danger?setConfirm(true):send(item.action)}><Power size={15}/>{item.title}</button></section>)}</div>
 <Panel title="命令与执行记录" extra={<span className="muted">最近 50 条 · 超时 {data.rules.command_timeout_seconds}s</span>}>{data.commands.length?<div className="table-wrap"><table><thead><tr><th>命令</th><th>发起人</th><th>创建时间</th><th>状态</th><th>设备回执</th></tr></thead><tbody>{data.commands.map(c=><tr key={c.id}><td><strong>{labels[c.action]}</strong><small>{c.id.slice(0,8)}</small></td><td>{c.requested_by}</td><td>{fmt(c.created_at)}</td><td><Badge value={c.status}/></td><td className="wide-cell">{c.result||'等待设备回执'}</td></tr>)}</tbody></table></div>:<Empty text="尚无控制命令，设备在线后可执行关阀、自检或消音"/>}</Panel>
 {confirm&&<Modal title="确认紧急关阀" onClose={()=>setConfirm(false)}><p>将向 <strong>{device?.name}</strong> 发送关阀命令。平台不会自动重新开阀。</p><Notice>页面将在收到设备回执后更新命令状态。模拟器回执不代表物理阀位。</Notice><div className="button-row"><button className="button danger" disabled={busy} onClick={()=>send('close_valve')}>确认发送</button><button className="button secondary" onClick={()=>setConfirm(false)}>取消</button></div></Modal>}
 </>;
}

/**
 * 文件职责：全站险情通知。
 * 主要功能：持续显示活动异常与待确认数量；用户开启后提供提示音和桌面通知。
 * 技术栈：React Hooks、Web Audio、Notification、aria-live。
 * 模块联动：App 传入实物快照，报警中心负责确认和处置；通知不撤销设备保护。
 * 编写/修改日期（日志对应）：2026-10-03、2026-10-13（实时通知）。
 */
import {useEffect,useRef,useState} from 'react';
import {Bell,Volume2} from 'lucide-react';
import type {Snapshot} from './types';
import {labels} from './components';

/** 每个报警的新触发、恢复和转人工独立提示，活动未确认异常每二十秒提醒。
 * 编写/修改日期（日志对应）：2026-10-13。 */
export function AlarmNotifier({data,openAlarms}:{data:Snapshot;openAlarms:()=>void}){
 const [sound,setSound]=useState(false),[desktop,setDesktop]=useState(false),[message,setMessage]=useState('');
 const audio=useRef<AudioContext|null>(null),seen=useRef(new Map<number,string>()),latest=useRef(data);
 latest.current=data;
 /** 音频必须由用户点击启动，只播放短提示，不改变 MCU 蜂鸣器。
  * 编写/修改日期（日志对应）：2026-10-13。 */
 const chime=()=>{const ctx=audio.current;if(!ctx||ctx.state!=='running')return;const oscillator=ctx.createOscillator(),gain=ctx.createGain();oscillator.frequency.value=880;gain.gain.setValueAtTime(.12,ctx.currentTime);gain.gain.exponentialRampToValueAtTime(.001,ctx.currentTime+.45);oscillator.connect(gain);gain.connect(ctx.destination);oscillator.start();oscillator.stop(ctx.currentTime+.45)};
 /** 点击后申请桌面通知权限，拒绝或不支持时保留页面内通知。
  * 编写/修改日期（日志对应）：2026-10-13。 */
 const enableDesktop=async()=>{if(!('Notification' in window)){setMessage('当前浏览器不支持桌面通知，请保持监控页面打开');return}const permission=await Notification.requestPermission();setDesktop(permission==='granted');setMessage(permission==='granted'?'桌面通知已开启；请保持此页面运行':'桌面通知未获授权，页面内提醒继续有效')};
 /** 快照变化时只通知状态发生变化的事件，普通心跳不重复弹出。
  * 编写/修改日期（日志对应）：2026-10-13。 */
 useEffect(()=>{
  const changes=data.alarms.filter(a=>{const state=`${a.status}:${!!a.response?.manual_required}:${!!a.acknowledged_at}`;const previous=seen.current.get(a.id);seen.current.set(a.id,state);return previous===undefined?a.status==='active':previous!==state});
  if(!changes.length)return;
  const alarm=changes.find(a=>a.kind==='fire')||changes[0];
  const text=`${labels[alarm.kind]||alarm.kind} #${alarm.id}：${alarm.status==='recovered'?(alarm.acknowledged_at?'信号恢复，保留人工确认记录':'信号恢复，记录仍需人工确认'):alarm.response?.manual_required?'需人工处置':alarm.message}`;
  setMessage(text);
  if(sound&&changes.some(a=>a.status==='active'&&!a.acknowledged_at))chime();
  if(desktop&&Notification.permission==='granted'&&document.visibilityState!=='visible'){
   const notification=new Notification('灶安 · 监测事件',{body:text,tag:`alarm-${alarm.id}`});
   notification.onclick=()=>{window.focus();openAlarms();notification.close()};
  }
 },[data,sound,desktop]);
 /** 未确认的活动异常定时再提醒，人工确认不会改变硬件保护。
  * 编写/修改日期（日志对应）：2026-10-13。 */
 useEffect(()=>{const timer=setInterval(()=>{if(sound&&latest.current.alarms.some(a=>a.status==='active'&&!a.acknowledged_at))chime()},20000);return()=>clearInterval(timer)},[sound]);
 useEffect(()=>()=>{void audio.current?.close()},[]);
 const count=data.stats.active_alarms;
 return <section className={`live-alert ${count?'has-danger':''}`} aria-label="实时报警通知">
  <div role={count?'alert':'status'} aria-live={count?'assertive':'polite'}><Bell size={19}/><div><strong>{count?`${count} 项活动异常`:'持续监测中'} · {data.stats.unacknowledged_alarms} 项待人工确认 · {data.stats.manual_required_alarms} 项需现场处置</strong><span>{message||'异常自动留档；自动恢复后仍保留人工确认'}</span></div></div>
  <div className="button-row"><button className="button secondary" onClick={async()=>{if(!audio.current)audio.current=new AudioContext();await audio.current.resume();setSound(!sound);if(!sound)chime()}}><Volume2 size={15}/>{sound?'关闭页面提示音':'开启页面提示音'}</button><button className="button secondary" onClick={()=>void enableDesktop()} disabled={desktop}>{desktop?'桌面通知已开启':'开启桌面通知'}</button><button className="button" onClick={openAlarms}>处理报警</button></div>
 </section>;
}

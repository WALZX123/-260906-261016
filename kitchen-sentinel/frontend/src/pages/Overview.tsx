/**
 * 文件职责：监控总览页面。
 * 主要功能：呈现相对指标、估算温度、趋势、设备来源、处置队列和输出状态。
 * 技术栈：React、TypeScript、Recharts、共享 UI 组件。
 * 模块联动：App 传入 Snapshot 和采样；调用 ResponseQueue、SensorReadings 与 sourceLabel，支持跳转报警和设备页面。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-03；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 总览页：把设备、报警、执行机构和实时曲线组合成现场工作台。
// 日志对应：2026-10-03 看板框架。硬件优先展示，原始量与未标定状态明确保留。
import {Activity,ArrowUpRight,Flame,Wifi,Wind,Thermometer,Radio} from 'lucide-react';
import {Badge,Chart,Empty,fmt,Panel} from '../components';
import type {Snapshot,Sample,Page} from '../types';
import {ResponseQueue} from '../ResponseQueue';
import {sourceLabel} from '../deviceView';

/** 接收设备快照与采样曲线，组合监测数值、设备来源和处置队列；相对指标与温度估算分别标明。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Overview({data,samples,navigate}:{data:Snapshot;samples:Sample[];navigate:(page:Page)=>void}){
 const device=data.devices[0];
 const current=device?.latest||{};
 // 来源决定测量口径；缺少热敏换算时不能显示虚构的摄氏度。
 const hardware=device?.source==='hardware';
 const metrics=[{label:'燃气相对指标',value:current.gas,unit:'/ 100',icon:Wind,color:'green',threshold:data.rules.gas_threshold},
  {label:'烟雾相对指标',value:current.smoke,unit:'/ 100',icon:Activity,color:'amber',threshold:data.rules.smoke_threshold},
  {label:hardware?'热敏温度估算':'环境温度',value:current.temperature,unit:'°C',icon:Thermometer,color:'blue',threshold:data.rules.temperature_threshold},
  {label:'火焰信号',value:current.monitoring_enabled===false?'待机':current.flame===undefined?'等待采样':current.flame?'检出':'未触发',unit:'',icon:Flame,color:'rose',threshold:null}];
 return <>
  <div className="metric-grid">{metrics.map(({label,value,unit,icon:Icon,color,threshold})=><section className={'metric '+color} key={label}><div className="metric-label"><span>{label}</span><Icon size={19}/></div><div className="metric-value">{value==null?'—':typeof value==='number'?value.toFixed(1):value}<small>{unit}</small></div><div className="metric-foot"><span className={'dot '+(!device?.online?'gray':'')}/>{!device?.online?'设备离线 · 显示最后读数':current.monitoring_enabled===false?'待机 · 请先开启硬件采样':current.test_scenario?'演练信号 · 原始通道保持真实':label==='烟雾相对指标'&&current.disabled_sensors?.includes('smoke')?'烟雾模块未接入':!current.valid?(hardware?'通道待标定':'采样异常 · 请检查设备'):threshold?`报警阈值 ${threshold} · 持续 ${data.rules.hold_seconds}s`:'触发后立即进入火灾报警'}</div></section>)}</div>
  <div className="grid-main"><Panel title="实时趋势" extra={<div className="legend"><span className="green">燃气</span><span className="amber">烟雾</span><span className="blue">温度</span><span className="muted">最近 90 条</span></div>}>{samples.length?<Chart data={samples} threshold={data.rules.gas_threshold}/>:<Empty text="等待所选设备上报数据"/>}<div className="panel-foot">燃气与烟雾为相对指标；温度单位为 °C。相对指标及估算温度待标定；通道诊断见系统测试。</div></Panel>
  <Panel title="现场设备" extra={<button className="text-button" onClick={()=>navigate('devices')}>查看详情 <ArrowUpRight size={15}/></button>}><div className="device-visual"><div className="device-icon"><Radio size={38}/><span className={'dot '+(!device?.online?'gray':'')}/></div><strong>{device?.name||'等待设备注册'}</strong><span>{device?.location||'—'}</span><Badge value={device?.online?'succeeded':'offline'}>{device?.online?'设备在线':'设备离线'}</Badge></div><div className="key-values"><div><span><Wifi size={14}/> 数据来源</span><b>{sourceLabel(device)}</b></div><div><span>最近上报</span><b>{device?.last_seen?new Date(device.last_seen).toLocaleTimeString('zh-CN',{hour12:false}):'尚未上报'}</b></div><div><span>本地报警</span><Badge value={current.local_alarm||'normal'}>{hardware&&current.local_alarm==='sensor_fault'?'通道待标定':undefined}</Badge></div></div></Panel></div>
  <ResponseQueue data={data} navigate={navigate}/>
  <div className="grid-main"><Panel title="近期报警" extra={<button className="text-button" onClick={()=>navigate('alarms')}>全部报警 <ArrowUpRight size={15}/></button>}>{data.alarms.length?<div className="table-wrap"><table><thead><tr><th>事件类型</th><th>触发时间</th><th>状态</th><th>人工确认</th></tr></thead><tbody>{data.alarms.slice(0,4).map(a=><tr key={a.id}><td><strong>{a.kind==='gas'?'燃气异常':a.kind==='fire'?'火灾异常':a.kind==='offline'?'设备离线':a.kind==='control_fault'?'控制执行异常':'采样异常'}</strong><small>#{String(a.id).padStart(5,'0')} · {a.device_id}</small></td><td>{fmt(a.started_at)}</td><td><Badge value={a.status}/></td><td>{a.acknowledged_at?'已确认':'待确认'}</td></tr>)}</tbody></table></div>:<Empty/>}</Panel><Panel title="联动状态"><div className="actuator-list">{[['valve','燃气阀门'],['fan','排风装置'],['power','低压继电器输出'],['buzzer','蜂鸣器']].map(([key,name])=><div key={key}><span>{name}</span><Badge value={device?.actuators[key]||'unknown'}>{device?.actuators[key]?(key==='power'?(device.actuators[key]==='on'?'保护输出有效':'未触发保护'):({'open':'开启','closed':'关闭','on':'开启','off':'关闭'} as Record<string,string>)[device.actuators[key]]):'等待反馈'}</Badge></div>)}</div><div className="panel-foot">{hardware?'状态来自控制引脚；阀门由舵机模拟，控制报告与机械动作分别核对。':'当前状态为模拟器反馈。'}</div></Panel></div>
 </>;
}

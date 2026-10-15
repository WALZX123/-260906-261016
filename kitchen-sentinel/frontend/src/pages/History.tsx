/**
 * 文件职责：遥测历史查询页面。
 * 主要功能：按设备与时段查询采样、显示趋势和明细，导出 CSV。
 * 技术栈：React Hooks、TypeScript、REST、URLSearchParams、Recharts。
 * 模块联动：调用 platform.history 和 export，复用 Chart 与时间格式；缺失量不显示成有效零值。
 * 编写/修改日期（日志对应）：2026-10-05；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 历史数据页：按时间范围查询遥测，并沿用总览图表组件展示趋势。
// 日志对应：2026-10-01 历史数据查询；2026-10-03 看板框架。硬件无效采样显示为待标定。
import {useEffect,useState} from 'react';
import {Download,Search} from 'lucide-react';
import {api} from '../api';
import {Chart,Empty,fmt,Panel,Badge,labels} from '../components';
import type {Sample,Snapshot} from '../types';
/** 管理设备和时间筛选，查询历史采样并复用同一参数导出 CSV，显示本次结果与数据质量。
 * 编写/修改日期（日志对应）：2026-10-05。 */
export function History({data,notify}:{data:Snapshot;notify:(s:string)=>void}){
 const [device,setDevice]=useState(data.devices[0]?.id||''),[start,setStart]=useState(''),[end,setEnd]=useState(''),[rows,setRows]=useState<Sample[]>([]),[busy,setBusy]=useState(false);
 /** 将选定设备和本地时间转为查询参数，时间统一传 ISO 格式，查询与导出复用同一条件。
  * 编写/修改日期（日志对应）：2026-10-05。 */
 const params=()=>{const p=new URLSearchParams({device_id:device,limit:'1000'});if(start)p.set('start',new Date(start).toISOString());if(end)p.set('end',new Date(end).toISOString());return p};
 /** 按共用查询参数请求历史采样，管理忙碌状态并在结束后恢复按钮。
  * 编写/修改日期（日志对应）：2026-10-05。 */
 const load=async()=>{if(!device){setRows([]);return}setBusy(true);try{setRows(await api<Sample[]>('/telemetry?'+params()))}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 /** 页面初次进入时按当前设备和条件加载历史，后续由查询按钮显式更新。
  * 编写/修改日期（日志对应）：2026-10-05。 */
 useEffect(()=>{void load()},[]);
 if(!data.devices.length)return <Empty text="尚未注册现场设备，接入后可查询历史"/>;
 return <><Panel title="历史查询" extra={<span className="muted">查询最多 1,000 条 · CSV 导出最多 5,000 条</span>}><div className="filter-bar"><label>设备<select value={device} onChange={e=>setDevice(e.target.value)}>{data.devices.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>开始时间<input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>结束时间<input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label><button className="button" onClick={load} disabled={busy}><Search size={16}/>{busy?'查询中':'查询记录'}</button><a className="button secondary" href={'/api/v1/telemetry/export?'+params()}><Download size={16}/>导出 CSV</a></div></Panel><Panel title="历史趋势" extra={<span className="muted">{rows.length} 条记录 · 与实时曲线使用同一数据源</span>}>{rows.length?<Chart data={rows}/>:<Empty text="该时间范围内暂无采样记录"/>}</Panel><Panel title="采样明细" extra={<span className="muted">显示本次查询最新 100 条</span>}><div className="table-wrap"><table><thead><tr><th>采样时间</th><th>燃气指标</th><th>烟雾指标</th><th>温度 °C</th><th>火焰</th><th>采样性质</th><th>数据质量</th><th>本地状态</th></tr></thead><tbody>{rows.slice(-100).reverse().map((r,i)=><tr key={r.id||i}><td>{fmt(r.sampled_at)}</td><td>{r.gas??'—'}</td><td>{r.smoke??'—'}</td><td>{r.temperature??'—'}</td><td>{r.flame?'检出':'未检出'}</td><td>{r.monitoring_enabled===false?'待机心跳':r.test_scenario?'实物演练 · '+(labels[r.test_scenario]||r.test_scenario):r.monitoring_enabled===true?'实际采样':'历史记录 · 未带性质标记'}</td><td><Badge value={r.valid?'succeeded':'sensor_fault'}>{r.valid?'有效':data.devices.find(d=>d.id===device)?.source==='hardware'?'待标定':'异常'}</Badge></td><td><Badge value={r.local_alarm}/></td></tr>)}</tbody></table></div></Panel></>;
}

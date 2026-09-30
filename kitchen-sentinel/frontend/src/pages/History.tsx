// 历史数据页：按时间范围查询遥测，并沿用总览图表组件展示趋势。
import {useEffect,useState} from 'react';
import {Download,Search} from 'lucide-react';
import {api} from '../api';
import {Chart,Empty,fmt,Panel,Badge} from '../components';
import type {Sample,Snapshot} from '../types';
export function History({data,notify}:{data:Snapshot;notify:(s:string)=>void}){
 const [device,setDevice]=useState(data.devices[0]?.id||'kitchen-001'),[start,setStart]=useState(''),[end,setEnd]=useState(''),[rows,setRows]=useState<Sample[]>([]),[busy,setBusy]=useState(false);
 const params=()=>{const p=new URLSearchParams({device_id:device,limit:'1000'});if(start)p.set('start',new Date(start).toISOString());if(end)p.set('end',new Date(end).toISOString());return p};
 const load=async()=>{setBusy(true);try{setRows(await api<Sample[]>('/telemetry?'+params()))}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 useEffect(()=>{void load()},[]);
 return <><Panel title="历史查询" extra={<span className="muted">查询最多 1,000 条 · CSV 导出最多 5,000 条</span>}><div className="filter-bar"><label>设备<select value={device} onChange={e=>setDevice(e.target.value)}>{data.devices.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>开始时间<input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>结束时间<input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label><button className="button" onClick={load} disabled={busy}><Search size={16}/>{busy?'查询中':'查询记录'}</button><a className="button secondary" href={'/api/v1/telemetry/export?'+params()}><Download size={16}/>导出 CSV</a></div></Panel><Panel title="历史趋势" extra={<span className="muted">{rows.length} 条记录 · 与实时曲线使用同一数据源</span>}>{rows.length?<Chart data={rows}/>:<Empty text="该时间范围内暂无采样记录"/>}</Panel><Panel title="采样明细" extra={<span className="muted">显示本次查询最新 100 条</span>}><div className="table-wrap"><table><thead><tr><th>采样时间</th><th>燃气指标</th><th>烟雾指标</th><th>温度 °C</th><th>火焰</th><th>数据质量</th><th>本地状态</th></tr></thead><tbody>{rows.slice(-100).reverse().map((r,i)=><tr key={r.id||i}><td>{fmt(r.sampled_at)}</td><td>{r.gas??'—'}</td><td>{r.smoke??'—'}</td><td>{r.temperature??'—'}</td><td>{r.flame?'检出':'未检出'}</td><td><Badge value={r.valid?'succeeded':'sensor_fault'}>{r.valid?'有效':'异常'}</Badge></td><td><Badge value={r.local_alarm}/></td></tr>)}</tbody></table></div></Panel></>;
}

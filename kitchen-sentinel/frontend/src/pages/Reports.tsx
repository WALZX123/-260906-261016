/** 文件职责：故障统计与周报月报；功能：主要故障排行、期间统计、DeepSeek专家分析及报告下载。
 * 技术栈：React、TypeScript、REST；关联archive统计、OperationReport，模型不控制硬件。
 * 编写/修改日期（日志对应）：2026-10-08、2026-10-15。 */
import {AnalysisContent,readableAnalysis} from '../AnalysisContent';
import {useEffect,useState} from 'react';
import {FileText,Download,Sparkles} from 'lucide-react';
import {api,post} from '../api';
import {Panel,Badge,Empty,fmt,labels} from '../components';
import type {Snapshot,User} from '../types';
/** 专家意见与调用状态；四类分析分别呈现，失败明确提示，不作为控制指令。 */
interface Advice{provider:string;model_status:string;model_error?:string;summary:string;evidence:string[];hypotheses:string[];recommendations:string[];uncertainties:string[]}
/** 完整期间的数据库聚合事实，实际时间窗口与结束标记决定统计边界。 */
interface Facts{statistics:Record<string,number|string|null>;faults:{kind:string;count:number;unacknowledged:number}[];window_start:string;window_end_exclusive:string;window_complete:boolean;limitations:string[]}
/** 已保存报告快照，生成者/日期、统计事实及分析意见共同用于回看和下载。 */
interface Report{id:number;period:string;created_at:string;created_by:string;facts:Facts;analysis:Advice}

/** 按自然周/月保存报告快照；只读用户可查询，只有可写角色能生成。 */
export function Reports({data,user,notify}:{data:Snapshot;user:User;notify:(s:string)=>void}){
 const [device,setDevice]=useState(data.devices[0]?.id||''),[period,setPeriod]=useState('weekly'),[anchor,setAnchor]=useState(new Date().toLocaleDateString('en-CA')),[useModel,setUseModel]=useState(true),[busy,setBusy]=useState(false),[reports,setReports]=useState<Report[]>([]),[selected,setSelected]=useState<Report|null>(null),[facts,setFacts]=useState<Facts|null>(null);
 /** 默认只查询统计和既有报告，不自动调用外部模型或产生费用。 */
 const load=async()=>{if(!device)return;try{const end=new Date(),start=new Date(end.getTime()-7*86400000);const [list,stats]=await Promise.all([api<Report[]>('/reports?device_id='+device),api<Facts>('/reports/statistics?'+new URLSearchParams({device_id:device,start:start.toISOString(),end:end.toISOString()}))]);setReports(list);setFacts(stats)}catch(e){notify((e as Error).message)}};
 // 切换设备时清空上一设备的报告详情，避免将不同节点的分析混在当前统计中。
 useEffect(()=>{setSelected(null);void load()},[device]);
 /** 显式生成才调用API；冻结事实与分析，模型失败仍保留带降级说明的统计报告。 */
 const generate=async()=>{setBusy(true);try{const r=await post<Report>('/reports',{device_id:device,period,anchor,use_model:useModel});setSelected(r);await load();notify(r.analysis.model_status==='succeeded'?'辅助分析运行报告已生成':r.analysis.model_error||'统计报告已生成')}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 return <><Panel title="运行报告与故障分析" extra={<Badge>统计事实 / 专家意见分别保存</Badge>}><div className="filter-bar"><label>设备<select value={device} onChange={e=>setDevice(e.target.value)}>{data.devices.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>周期<select value={period} onChange={e=>setPeriod(e.target.value)}><option value="weekly">自然周报</option><option value="monthly">自然月报</option></select></label><label>期间内日期<input type="date" value={anchor} onChange={e=>setAnchor(e.target.value)}/></label><label className="checkbox-label"><input type="checkbox" checked={useModel} onChange={e=>setUseModel(e.target.checked)}/>模型辅助分析</label>{user.role!=='viewer'&&<button className="button" disabled={busy||!device} onClick={generate}><Sparkles size={16}/>{busy?'正在分析，监测继续运行…':'生成报告'}</button>}<button className="button secondary" onClick={load}>刷新统计</button></div><p className="muted">周报按周一到下周一，月报按自然月，采用北京时间。尚未结束的期间只分析已有记录。</p></Panel>
 <div className="archive-summary"><div><span>近七日存档</span><strong>{Number(facts?.statistics.sample_count||0).toLocaleString()}</strong></div><div><span>离线补传</span><strong>{Number(facts?.statistics.backfill_count||0).toLocaleString()}</strong></div><div><span>期间相关异常</span><strong>{facts?.faults.reduce((sum,f)=>sum+f.count,0)??0}</strong></div></div>
 <div className="report-columns"><Panel title="近七日主要异常"><p className="muted">统计包含实物演练；未标记的历史事件不等于已确认事故。</p>{facts?.faults.length?<div className="fault-ranking">{facts.faults.map(f=><div key={f.kind}><div><strong>{labels[f.kind]||f.kind}</strong><span>{f.count}项 · {f.unacknowledged}项待确认</span></div><meter min="0" max={Math.max(...facts.faults.map(x=>x.count))} value={f.count}/></div>)}</div>:<Empty text="该期间没有异常记录"/>}</Panel><Panel title="已保存报告">{reports.length?<div className="report-list">{reports.map(r=><button className={selected?.id===r.id?'selected':''} key={r.id} onClick={()=>setSelected(r)}><FileText size={18}/><span><strong>{r.period==='weekly'?'运行周报':'运行月报'} #{r.id}</strong><small>{fmt(r.created_at)} · {r.analysis.provider==='rules'?'规则统计':'模型辅助分析'}</small></span></button>)}</div>:<Empty text="生成报告后将保存在这里"/>}</Panel></div>
 {selected&&<Panel title={`${selected.period==='weekly'?'运行周报':'运行月报'} #${selected.id}`} extra={<a className="button secondary" href={`/api/v1/reports/${selected.id}/download`}><Download size={16}/>下载报告</a>}><p className="muted">{fmt(selected.facts.window_start)} 至 {fmt(selected.facts.window_end_exclusive)}（不含结束时刻）{!selected.facts.window_complete?' · 当前期间尚未结束':''}</p><Badge>{selected.analysis.model_status==='succeeded'?'模型辅助分析':'规则统计版'}</Badge>{selected.analysis.model_error&&<p>{selected.analysis.model_error}</p>}<p className="muted">统计期间采用北京时间；分析基于已保存的事实，不改变报警确认与保护动作。</p><AnalysisContent advice={selected.analysis}/><p className="muted">{readableAnalysis(selected.facts.limitations.join(' '))}</p></Panel>}</>;
}

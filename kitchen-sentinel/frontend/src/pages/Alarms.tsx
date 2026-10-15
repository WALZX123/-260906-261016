/**
 * 文件职责：异常历史与人员处理页面。
 * 主要功能：筛选事件，展示时间线，记录确认、备注、现场异常升级及处置完成，生成摘要。
 * 技术栈：React Hooks、TypeScript、REST、状态标签和弹窗。
 * 模块联动：对接 platform 报警接口，复用 ResponseStatus；自动恢复不代替人员确认，现场处置不下发开阀命令。
 * 编写/修改日期（日志对应）：2026-10-05；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 日志对应：2026-10-03。确认只表示收到报警，自动响应和人工处置另行记录。
// 报警中心：展示报警生命周期、人工确认、备注和规则摘要。
import {ResponseTags,ResponseDetails} from '../ResponseStatus';
import {useEffect,useState} from 'react';
import {ArrowUpRight,CheckCheck,FileText,Sparkles} from 'lucide-react';
import {api,post} from '../api';
import {Badge,Empty,fmt,Modal,Notice,Panel,labels} from '../components';
import type {Alarm,Snapshot,User,Analysis} from '../types';

/** 管理事件筛选、详情和处理说明，通过专用接口分别提交确认、升级及处置记录。
 * 编写/修改日期（日志对应）：2026-10-05。 */
export function Alarms({data,user,refresh,notify,scope='hardware'}:{data:Snapshot;user:User;refresh:()=>Promise<void>;notify:(s:string)=>void;scope?:'hardware'|'simulated'}){
 const [filter,setFilter]=useState('all'),[selected,setSelected]=useState<Alarm|null>(null),[note,setNote]=useState(''),[busy,setBusy]=useState(false),[older,setOlder]=useState<Alarm[]>([]),[historyBefore,setHistoryBefore]=useState<number|null>(null),[historyEnd,setHistoryEnd]=useState(false);
 /** 实时快照到达时同步当前详情事件，保留页面筛选并显示最新确认与处置状态。
  * 编写/修改日期（日志对应）：2026-10-05。 */
 useEffect(()=>{if(selected){const updated=data.alarms.find(a=>a.id===selected.id);if(updated)setSelected(updated)}},[data]);
 const rows=[...data.alarms,...older.filter(a=>!data.alarms.some(x=>x.id===a.id))].filter(a=>filter==='all'||(filter==='unacknowledged'?!a.acknowledged_at:filter==='manual'?a.response?.manual_required:a.status===filter));
 /** 依据操作种类调用确认、备注、摘要、升级或处置接口；写入前要求说明，并刷新所选事件。
  * 编写/修改日期（日志对应）：2026-10-05。 */
 const act=async(kind:'acknowledge'|'notes'|'analysis'|'resolve'|'escalate',model=false)=>{if(!selected)return;if(kind!=='analysis'&&!note.trim()){notify('请先填写处理说明');return}setBusy(true);try{const result=await post<Alarm|Analysis>(`/alarms/${selected.id}/${kind}${model?'?use_model=true':''}`,kind==='analysis'?{}:{note});if(kind==='analysis')setSelected({...selected,analysis:result as Analysis});else setSelected(result as Alarm);setNote('');await refresh();notify(kind==='analysis'?'分析已生成':'处理记录已保存')}catch(e){notify((e as Error).message)}finally{setBusy(false)}};
 return <><div className="summary-strip"><div><b>{data.stats.active_alarms}</b><span>当前触发</span></div><div><b>{data.stats.unacknowledged_alarms}</b><span>待人工确认</span></div><div><b>{data.alarms.filter(a=>a.status==='recovered').length}</b><span>条件已恢复</span></div><p>活动和待确认数量统计全部记录。自动响应、信号恢复与人工处置分别留档。</p></div><Panel title="报警事件" extra={<div className="tabs">{[['all','全部'],['active','触发中'],['unacknowledged','报警待确认'],['manual','需人工处置'],['recovered','已恢复']].map(([k,v])=><button className={filter===k?'selected':''} onClick={()=>setFilter(k)} key={k}>{v}</button>)}</div>}>
 {rows.length?<div className="table-wrap"><table><thead><tr><th>事件编号 / 类型</th><th>触发原因</th><th>时间</th><th>状态</th><th>处理</th></tr></thead><tbody>{rows.map(a=><tr key={a.id}><td><strong>#{String(a.id).padStart(5,'0')} {labels[a.kind]}</strong><small>{a.device_id}{a.evidence.test_scenario?' · 实物演练：'+(labels[String(a.evidence.test_scenario)]||String(a.evidence.test_scenario)):''}</small></td><td className="wide-cell">{a.message}</td><td>{fmt(a.started_at)}</td><td><Badge value={a.status}/><ResponseTags alarm={a}/></td><td><button className="text-button" onClick={()=>{setSelected(a);setNote('')}}>{a.acknowledged_at?'查看记录':'查看并处理'} <ArrowUpRight size={14}/></button></td></tr>)}</tbody></table></div>:<Empty/>}<div className="panel-foot"><button className="text-button" disabled={historyEnd} onClick={()=>api<Alarm[]>(`/alarms?scope=${scope}&limit=100${historyBefore===null?'':'&before_id='+historyBefore}`).then(more=>{setOlder(prev=>[...prev,...more.filter(a=>!prev.some(x=>x.id===a.id))]);if(more.length)setHistoryBefore(more[more.length-1].id);if(more.length<100){setHistoryEnd(true);notify('已经加载全部历史报警')}}).catch(e=>notify(e.message))}>{historyEnd?'历史记录已全部加载':'加载历史记录'}</button></div></Panel>
 {selected&&<Modal title={`报警详情 #${String(selected.id).padStart(5,'0')}`} onClose={()=>setSelected(null)}><div className="detail-heading"><Badge value={selected.kind}/><Badge value={selected.status}/><span className="muted">{selected.acknowledged_at?`${selected.acknowledged_by} 已确认`:'尚未人工确认'}</span></div><p>{selected.message}</p>{!!selected.evidence.test_scenario&&<Notice>实物演练 · {labels[String(selected.evidence.test_scenario)]||String(selected.evidence.test_scenario)}；保护输入由限时注入产生，原始通道保留真实采样。</Notice>}<div className="detail-grid"><div><label>触发时间</label>{fmt(selected.started_at)}</div><div><label>恢复时间</label>{fmt(selected.recovered_at)}</div></div><h3>自动响应与人工升级</h3><ResponseDetails alarm={selected}/><h3>事件时间线</h3><div className="timeline">{selected.timeline.map((item,i)=><div key={i}><time>{fmt(item.at)}</time><p>{item.message}</p></div>)}</div><h3>事件分析</h3>{selected.analysis?<div className="analysis"><Badge>{selected.analysis.provider==='rules'?'规则摘要':`模型辅助 · ${selected.analysis.provider}`}</Badge><p className="prewrap">{selected.analysis.summary}</p><div className="analysis-stats"><span>样本 {selected.analysis.sample_count}</span><span>燃气峰值 {selected.analysis.peak_gas??'—'}</span><span>温度峰值 {selected.analysis.peak_temperature??'—'} °C</span></div><small>{selected.analysis.limitations}</small></div>:<p className="muted">基于事件期间的采样记录生成摘要，分析不会改变保护动作。</p>}
 {user.role!=='viewer'&&<><div className="button-row"><button className="button secondary" disabled={busy} onClick={()=>act('analysis')}><FileText size={16}/>生成规则摘要</button><button className="button secondary" disabled={busy} onClick={()=>act('analysis',true)}><Sparkles size={16}/>调用模型分析</button></div><h3>处理记录</h3><textarea value={note} onChange={e=>setNote(e.target.value)} placeholder="记录核查情况或处理措施，最多 500 字" maxLength={500}/><div className="button-row"><button className="button" disabled={busy||!!selected.acknowledged_at} onClick={()=>act('acknowledge')}><CheckCheck size={16}/>确认收到报警</button>{selected.response?.manual_required&&<button className='button secondary' disabled={busy||selected.status==='active'||!selected.acknowledged_at} onClick={()=>act('resolve')}>记录现场处置完成</button>}<button className="button secondary" disabled={busy} onClick={()=>act('notes')}>追加备注</button></div></>}
 {user.role!=='viewer'&&<button className="button secondary" disabled={busy} onClick={()=>act('escalate')}>报告现场异常并转人工</button>}
 <Notice>确认报警不会关闭持续异常，也不会重新开阀。现场发现执行器没有动作，可填写说明并转人工；火灾、超限或响应超时自动升级人工处置。</Notice></Modal>}
 </>;
}

// 操作审计页：只读展示管理员操作与系统关键事件。
import {useEffect,useState} from 'react';
import {RefreshCw} from 'lucide-react';
import {api} from '../api';
import {Empty,fmt,Panel} from '../components';
import type {Audit as AuditRow} from '../types';
export function Audit({notify}:{notify:(s:string)=>void}){
 const [rows,setRows]=useState<AuditRow[]>([]);
 const load=()=>api<AuditRow[]>('/audit?limit=200').then(setRows).catch(e=>notify(e.message));
 useEffect(()=>{void load()},[]);
 return <Panel title="操作审计" extra={<button className="button secondary" onClick={load}><RefreshCw size={15}/>刷新</button>}>{rows.length?<div className="table-wrap"><table><thead><tr><th>时间</th><th>操作人</th><th>操作类型</th><th>关联对象</th><th>记录内容</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{fmt(r.created_at)}</td><td>{r.actor}</td><td><code>{r.action}</code></td><td>{r.target||'—'}</td><td className="wide-cell audit-detail">{Object.keys(r.detail).length?JSON.stringify(r.detail):'—'}</td></tr>)}</tbody></table></div>:<Empty/>}<div className="panel-foot">最近 200 条。日志保存在数据库中，用于追踪登录、规则修改、报警处理和控制命令。</div></Panel>;
}

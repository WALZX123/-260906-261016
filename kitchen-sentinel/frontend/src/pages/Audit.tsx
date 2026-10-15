/**
 * 文件职责：操作审计查询页面。
 * 主要功能：读取并展示操作人、时间、动作、目标和审计详情。
 * 技术栈：React Hooks、TypeScript、REST、只读表格。
 * 模块联动：调用 platform.audit，App 只向管理员提供入口；日志由后端认证、规则、报警与命令流程写入。
 * 编写/修改日期（日志对应）：2026-10-05。
 */
// 操作审计页：只读展示管理员操作与系统关键事件。
import {useEffect,useState} from 'react';
import {RefreshCw} from 'lucide-react';
import {api} from '../api';
import {Empty,fmt,Panel} from '../components';
import type {Audit as AuditRow} from '../types';
/** 只读呈现最近审计日志，刷新失败通过共享提示通知，便于追踪人员与系统动作。
 * 编写/修改日期（日志对应）：2026-10-05。 */
export function Audit({notify}:{notify:(s:string)=>void}){
 const [rows,setRows]=useState<AuditRow[]>([]);
 /** 读取最近审计日志并更新只读表格，错误通过 notify 提示。
  * 编写/修改日期（日志对应）：2026-10-05。 */
 const load=()=>api<AuditRow[]>('/audit?limit=200').then(setRows).catch(e=>notify(e.message));
 /** 页面初次进入时加载审计，后续由刷新按钮重新读取。
  * 编写/修改日期（日志对应）：2026-10-05。 */
 useEffect(()=>{void load()},[]);
 return <Panel title="操作审计" extra={<button className="button secondary" onClick={load}><RefreshCw size={15}/>刷新</button>}>{rows.length?<div className="table-wrap"><table><thead><tr><th>时间</th><th>操作人</th><th>操作类型</th><th>关联对象</th><th>记录内容</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{fmt(r.created_at)}</td><td>{r.actor}</td><td><code>{r.action}</code></td><td>{r.target||'—'}</td><td className="wide-cell audit-detail">{Object.keys(r.detail).length?JSON.stringify(r.detail):'—'}</td></tr>)}</tbody></table></div>:<Empty/>}<div className="panel-foot">最近 200 条。日志保存在数据库中，用于追踪登录、规则修改、报警处理和控制命令。</div></Panel>;
}

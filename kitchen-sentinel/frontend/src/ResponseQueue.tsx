/**
 * 文件职责：首页自动响应与人工核查队列。
 * 主要功能：汇总待确认和待处置数量，优先展示需人工处理的事件并提供详情入口。
 * 技术栈：React、TypeScript、Snapshot 聚合与数组筛选。
 * 模块联动：Overview 提供快照和页面跳转，ResponseStatus 统一状态标签；恢复不移除待确认记录。
 * 编写/修改日期（日志对应）：2026-10-05；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 日志对应：2026-10-03。首页同时显示自动响应、待确认报警和需人工处置事件。
import {Badge,Panel} from './components';
import {ResponseTags} from './ResponseStatus';
import type {Page,Snapshot} from './types';

/** 从最近快照筛出活动、未确认或待人工处置事件，按人工要求优先展示，并提供报警页面跳转。
 * 编写/修改日期（日志对应）：2026-10-05。 */
export function ResponseQueue({data,navigate}:{data:Snapshot;navigate:(page:Page)=>void}){
 const rows=data.alarms.filter(a=>a.status==='active'||!a.acknowledged_at||a.response?.manual_required)
  .sort((a,b)=>Number(!!b.response?.manual_required)-Number(!!a.response?.manual_required)).slice(0,4);
 return <Panel title="自动响应与人工核查" extra={<button className="text-button" onClick={()=>navigate('alarms')}>进入报警中心</button>}>
  <div className="response-tags"><Badge>{data.stats.unacknowledged_alarms||0} 条报警待确认</Badge><Badge value={data.stats.manual_required_alarms?'fire':'succeeded'}>{data.stats.manual_required_alarms||0} 条需人工处置</Badge><span className="muted">全量事件统计 · 优先展示待处理项</span></div>
  <p className="muted">系统能力范围内先自动响应并观察效果；火灾、超限或响应超时升级人工。确认报警不影响自动保护。</p>
  {rows.map(alarm=><div className="response-row" key={alarm.id}><strong>#{alarm.id} · {alarm.message}</strong><small>{alarm.device_id}</small><ResponseTags alarm={alarm}/></div>)}
 </Panel>;
}

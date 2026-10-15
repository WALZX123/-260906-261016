/**
 * 文件职责：前后端数据类型契约。
 * 主要功能：定义用户、采样、设备、报警响应、规则、命令、快照和页面枚举。
 * 技术栈：TypeScript interface、联合类型、可空字段。
 * 模块联动：对应 FastAPI schemas 和 monitoring.serialize，供所有页面、api 泛型和监控 Hook 校验字段使用。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-09-21；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 前后端共享的数据形状；字段名称与 FastAPI 序列化结果保持一致。
// 日志对应：2026-09-21 统一采集结构；2026-10-03 看板框架。raw 为原始量，温度可为空。
/** 登录用户和页面权限资料；CSRF 仅用于后续写请求。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface User {username:string;role:'admin'|'operator'|'viewer';csrf_token:string}
/** 统一遥测结构，保留缺失测量、原始通道、滤波、实际传输方式和标定状态。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Sample {id?:number;device_id?:string;boot_id?:string;sequence?:number;sampled_at:string;received_at?:string;gas:number|null;smoke:number|null;temperature:number|null;flame:boolean;valid:boolean;local_alarm:string;transport?:string|null;disabled_sensors?:string[];filtered?:Sample["raw"];raw?:Partial<Record<'smoke_ao'|'temp_ao'|'gas_ao'|'flame_ao'|'smoke_do'|'flame_do',number|null>>|null;control_capabilities?:string[];diagnostics?:Record<string,number>;monitoring_enabled?:boolean;test_scenario?:string}
/** 设备身份、在线情况、最新采样与控制输出；不同来源节点独立保存。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Device {id:string;name:string;location:string;source:string;online:boolean;last_seen:string|null;latest:Partial<Sample>;actuators:Record<string,string>;scenario:string;firmware:string}
/** 规则或模型摘要结果与样本数量、峰值和限制，不能作为执行器控制指令。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Analysis {provider:string;summary:string;sample_count:number;peak_gas:number|null;peak_temperature:number|null;limitations:string;generated_at:string}
/** 自动响应进度、人工升级原因、动作比对和现场处置记录，不代替报警确认字段。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface AlarmResponse {automatic_status:string;manual_required:boolean;reasons:string[];actions:{actuator:string;expected:string;reported:string|null;matched:boolean}[];feedback_level:string;resolution:{at:string;by:string;note:string}|null}
/** 独立异常事件及其触发、恢复、人员确认、证据、时间线和分析结果。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Alarm {id:number;device_id:string;kind:string;severity:string;status:string;message:string;started_at:string;recovered_at:string|null;acknowledged_at:string|null;acknowledged_by:string|null;timeline:{at:string;message:string}[];evidence:Record<string,unknown>;analysis:Analysis|null;response:AlarmResponse}
/** 控制命令从创建到回执或超时的记录，用于区分指令下发和执行结果。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Command {id:string;device_id:string;action:string;status:string;requested_by:string;created_at:string;completed_at:string|null;result:string|null}
/** 带修订号的阈值、恢复与观察时限配置，供页面校验和服务端规则同步。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Rules {revision:number;gas_threshold:number;smoke_threshold:number;temperature_threshold:number;hold_seconds:number;recovery_seconds:number;hysteresis:number;offline_seconds:number;command_timeout_seconds:number;gas_manual_threshold:number;auto_response_timeout_seconds:number}
/** 后端周期快照，聚合设备、报警、命令、规则及统计；REST 与 WebSocket 共用。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Snapshot {server_time:string;devices:Device[];alarms:Alarm[];commands:Command[];rules:Rules;stats:{devices:number;online:number;active_alarms:number;unacknowledged_alarms:number;manual_required_alarms:number;pending_commands:number}}
/** 关键操作的人员、目标、日期时间和附加详情，供管理员追溯。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export interface Audit {id:number;actor:string;action:string;target:string;created_at:string;detail:Record<string,unknown>}
/** 工作台允许跳转的页面标识，与 App 菜单和页面组件保持一致。
 * 编写/修改日期（日志对应）：2026-09-21。 */
export type Page = 'activation'|'overview'|'devices'|'alarms'|'control'|'history'|'settings'|'audit'|'testing';

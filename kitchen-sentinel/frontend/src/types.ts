// 前后端共享的数据形状；字段名称与 FastAPI 序列化结果保持一致。
export interface User {username:string;role:'admin'|'operator'|'viewer';csrf_token:string}
export interface Sample {id?:number;sampled_at:string;received_at?:string;gas:number|null;smoke:number|null;temperature:number|null;flame:boolean;valid:boolean;local_alarm:string}
export interface Device {id:string;name:string;location:string;source:string;online:boolean;last_seen:string|null;latest:Partial<Sample>;actuators:Record<string,string>;scenario:string;firmware:string}
export interface Analysis {provider:string;summary:string;sample_count:number;peak_gas:number|null;peak_temperature:number|null;limitations:string;generated_at:string}
export interface Alarm {id:number;device_id:string;kind:string;severity:string;status:string;message:string;started_at:string;recovered_at:string|null;acknowledged_at:string|null;acknowledged_by:string|null;timeline:{at:string;message:string}[];evidence:Record<string,unknown>;analysis:Analysis|null}
export interface Command {id:string;device_id:string;action:string;status:string;requested_by:string;created_at:string;completed_at:string|null;result:string|null}
export interface Rules {revision:number;gas_threshold:number;smoke_threshold:number;temperature_threshold:number;hold_seconds:number;recovery_seconds:number;hysteresis:number;offline_seconds:number;command_timeout_seconds:number}
export interface Snapshot {server_time:string;devices:Device[];alarms:Alarm[];commands:Command[];rules:Rules;stats:{devices:number;online:number;active_alarms:number;pending_commands:number}}
export interface Audit {id:number;actor:string;action:string;target:string;created_at:string;detail:Record<string,unknown>}
export type Page = 'overview'|'devices'|'alarms'|'control'|'history'|'settings'|'audit';

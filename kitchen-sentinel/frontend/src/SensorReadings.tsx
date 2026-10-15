/**
 * 文件职责：实物传感器原始通道表。
 * 主要功能：并列显示 ADC 原始值、八点均值、数字触发和隔离通道。
 * 技术栈：React、TypeScript、可空 Sample、HTML 表格。
 * 模块联动：由系统测试页传入采样，字段来自固件状态块和 SWD 网关；显示估算与未标定边界。
 * 编写/修改日期（日志对应）：2026-10-03；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 日志对应：2026-09-22 滤波；2026-10-03 看板。原始量与均值并排展示，数字输入不求均值。
import type {Sample} from './types';

const channels:[keyof NonNullable<Sample['raw']>,string][]=[
 ['gas_ao','电位器'],['smoke_ao','烟雾'],['temp_ao','热敏'],['flame_ao','火焰'],
 ['smoke_do','烟雾数字触发'],['flame_do','火焰数字触发'],
];

/** 接收可缺失的 Sample，按通道并列显示原始量、均值和量程；缺失值及隔离通道明确标记。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function SensorReadings({sample}:{sample:Partial<Sample>}){
 return <div className="table-wrap"><table><thead><tr><th>通道</th><th>当前原始值</th><th>8 点滑动均值</th><th>量程</th></tr></thead>
  <tbody>{channels.map(([key,label])=><tr key={key}><td>{label}{key.startsWith('smoke')&&sample.disabled_sensors?.includes('smoke')?'（未接入）':''}</td><td>{sample.raw?.[key]??'—'}</td><td>{sample.filtered?.[key]??'—'}</td><td>{key.endsWith('_do')?'0 / 1':'0–4095'}</td></tr>)}</tbody>
 </table><div className="panel-foot">相对指标和温度估算使用滤波值；火焰数字触发实时参与保护，烟雾 DO 用于诊断。温度按标称 NTC 参数换算，尚未实物标定。</div></div>;
}

/**
 * 文件职责：全站共用的展示组件。
 * 主要功能：提供状态标签、时间格式、空状态、面板、趋势图、弹窗和提示条。
 * 技术栈：React、TypeScript、Recharts、Lucide、CSS。
 * 模块联动：各 pages 复用本模块；Chart 使用 Sample，报警恢复标签与人工确认状态分开。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-03；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 修改日期（对应实习日志）：2026-10-03。统一标签、图表和弹窗；信号恢复与人工确认分别显示。
import {Area,CartesianGrid,ComposedChart,Line,ResponsiveContainer,Tooltip,XAxis,YAxis,ReferenceLine} from 'recharts';
import {X,ShieldCheck,AlertTriangle,Clock3} from 'lucide-react';
import type {ReactNode} from 'react';
import type {Sample} from './types';
export const labels:Record<string,string>={smoke:'烟雾报警',temperature:'高温报警',flame:'火焰报警',start_monitoring:'开启硬件采样',stop_monitoring:'暂停采样并关阀',open_valve:'恢复运行并开阀',inject_gas:'燃气演练',inject_smoke:'烟雾演练',inject_temperature:'高温演练',inject_flame:'火焰演练',inject_multiple:'复合险情演练',cancel_injection:'结束演练',test_buzzer:'蜂鸣器测试',test_fan:'风扇测试',test_relay:'继电器测试',test_servo:'舵机关阀测试',gas:'燃气报警',fire:'火灾报警',control_fault:'控制执行异常',sensor_fault:'传感器故障',offline:'设备离线',normal:'正常监测',multiple:'多项报警',active:'触发中',recovered:'信号已恢复',pending:'等待下发',dispatched:'已下发',succeeded:'执行成功',failed:'执行失败',timeout:'执行超时',close_valve:'紧急关阀',silence:'暂时消音',self_test:'设备自检',admin:'管理员',operator:'操作员',viewer:'观察员',open:'开启',closed:'关闭',on:'开启',off:'关闭',spike:'瞬时尖峰',command_timeout:'命令超时'};
/** 把后端带时区时间转换为中文本机时间，空值统一显示占位符。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export const fmt=(s:string|null|undefined)=>s?new Date(s).toLocaleString('zh-CN',{hour12:false}):'—';
/** 把状态键或显式内容渲染为统一标签，中文名称与样式由共享状态映射决定。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Badge({value,children}:{value?:string;children?:ReactNode}){return <span className={`badge ${value||''}`}>{children||labels[value||'']||value}</span>}
/** 为没有记录的面板显示明确空状态，允许页面传入符合当前查询的说明。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Empty({text='暂无符合条件的记录'}:{text?:string}){return <div className="empty"><ShieldCheck size={32}/><p>{text}</p></div>}
/** 统一页面区块的标题、右侧操作和内容布局，供各业务页面组合使用。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Panel({title,extra,children,className=''}:{title:string;extra?:ReactNode;children:ReactNode;className?:string}){return <section className={'panel '+className}><div className="panel-head"><h2>{title}</h2>{extra}</div>{children}</section>}
/** 根据采样数组绘制燃气、烟雾与温度趋势，可显示燃气阈值；空值保持断点以免掩盖无效采样。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Chart({data,threshold}:{data:Sample[];threshold?:number}){return <div className="chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data}><defs><linearGradient id="gasFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#118477" stopOpacity={.23}/><stop offset="100%" stopColor="#118477" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e4e9e6"/><XAxis dataKey="sampled_at" tickFormatter={s=>new Date(s).toLocaleTimeString('zh-CN',{hour12:false})} minTickGap={55} tick={{fontSize:11,fill:'#78867f'}} axisLine={false} tickLine={false}/><YAxis domain={[0,100]} tick={{fontSize:11,fill:'#78867f'}} axisLine={false} tickLine={false} width={30}/><Tooltip labelFormatter={s=>fmt(String(s))} contentStyle={{borderRadius:10,borderColor:'#dde5df',fontSize:12}}/>{threshold&&<ReferenceLine y={threshold} stroke="#c48845" strokeDasharray="6 5" label={{value:'燃气阈值',fill:'#a2723c',fontSize:11,position:'insideTopRight'}}/>}<Area type="monotone" dataKey="gas" name="燃气相对指标" stroke="#118477" fill="url(#gasFill)" strokeWidth={2.5} isAnimationActive={false} connectNulls={false}/><Line type="monotone" dataKey="smoke" name="烟雾相对指标" stroke="#dcaa52" strokeWidth={2} dot={false} isAnimationActive={false}/><Line type="monotone" dataKey="temperature" name="温度 °C" stroke="#7691b4" strokeWidth={2} dot={false} isAnimationActive={false}/></ComposedChart></ResponsiveContainer></div>}
/** 提供可访问的详情弹窗，背景或关闭按钮触发回调，弹窗内部点击不穿透到背景。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){return <div className="modal-backdrop" onClick={onClose}><section className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={e=>e.stopPropagation()}><div className="panel-head"><h2>{title}</h2><button className="icon-button" aria-label="关闭" onClick={onClose}><X/></button></div>{children}</section></div>}
/** 按普通或警告状态渲染说明条，供标定边界、权限和人工处置提示复用。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Notice({children,warn=false}:{children:ReactNode;warn?:boolean}){return <div className={'notice '+(warn?'warning':'')} >{warn?<AlertTriangle size={17}/>:<Clock3 size={17}/>}<span>{children}</span></div>}

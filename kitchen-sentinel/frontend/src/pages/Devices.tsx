/**
 * 文件职责：设备详情页面。
 * 主要功能：显示节点身份、在线状态、实际数据来源、原始通道和控制输出。
 * 技术栈：React、TypeScript、HTML 表格、共享组件。
 * 模块联动：App 提供设备快照，复用 SensorReadings 与 sourceLabel；硬件节点和模拟节点分别显示。
 * 编写/修改日期（日志对应）：2026-10-03；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
// 设备页：展示设备身份、在线状态、采样通道和当前执行机构状态。
// 日志对应：2026-10-03 看板框架。设备身份分开保存，控制寄存器不等同于物理动作反馈。
import {Cpu,Wifi,Radio,Link2} from 'lucide-react';
import {Badge,fmt,Notice,Panel} from '../components';
import type {Snapshot} from '../types';
import {sourceLabel} from '../deviceView';

/** 逐节点展示身份、在线情况、原始通道和输出状态，保持硬件与模拟来源对应。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function Devices({data}:{data:Snapshot}){
 return <><Notice>本页显示现场设备。原始通道诊断和执行器分项检查位于系统测试。</Notice>
  {data.devices.map(d=><Panel key={d.id} title={d.name} extra={<Badge value={d.online?'succeeded':'offline'}>{d.online?'在线':'离线'}</Badge>}>
   <div className="device-detail"><div className="device-big"><Cpu size={60}/><h3>{d.id}</h3><Badge>{d.source==='hardware'?'硬件设备':'模拟设备'}</Badge></div>
    <div className="detail-grid"><div><label>安装位置</label>{d.location}</div><div><label>固件标识</label>{d.firmware}</div><div><label>最近心跳</label>{fmt(d.last_seen)}</div><div><label>数据来源</label>{sourceLabel(d)}</div><div><label>传感器通道</label>燃气相对通道 / 烟雾 / 热敏 / 火焰</div><div><label>执行机构</label>舵机模拟阀门 / 风扇 / 低压继电器 / 蜂鸣器</div></div>
   </div>
   {d.source==='hardware'&&<><Notice>控制状态来自 MCU 引脚和定时器寄存器，其他执行器的物理动作仍需实物核对。远程能力以设备实际上报为准。</Notice></>}
   <div className="integration-flow"><span><Radio size={18}/>采集模块</span><i>→</i><span><Cpu size={18}/>现场控制器</span><i>→</i><span><Wifi size={18}/>电脑网关</span><i>→</i><span><Link2 size={18}/>监控平台</span></div>
   <div className="panel-foot">设备令牌不在页面展示。硬件 ADC 范围为 0–4095，未经标定不能当作气体浓度，热敏温度为标称参数估算。</div>
  </Panel>)}
 </>;
}

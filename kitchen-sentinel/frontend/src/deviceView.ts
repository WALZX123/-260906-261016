/**
 * 文件职责：设备数据来源的显示转换。
 * 主要功能：区分等待上报、模拟器、SWD 实物和 TCP 实物来源。
 * 技术栈：TypeScript、Device 类型和传输字段。
 * 模块联动：Overview 与 Devices 调用 sourceLabel；来源按设备实际上报内容判断，不能把 SWD 显示成 Wi-Fi 连通。
 * 编写/修改日期（日志对应）：2026-10-03。
 */
import type {Device} from './types';

// 日志对应：2026-10-03 看板框架。来源按实际传输方式显示，SWD 接入不能标成 Wi-Fi 已连接。
/** 把设备身份与实际上报的传输方式转换为中文来源标签，缺少节点时显示等待上报。
 * 编写/修改日期（日志对应）：2026-10-03。 */
export function sourceLabel(device?:Device){
 if(!device)return '等待设备上报';
 if(device.source!=='hardware')return '设备模拟器';
 const transport=device.latest.transport;
 return transport==='swd'?'STM32 实物采样 · 调试器连接':transport==='tcp'?'STM32 实物采样 · Wi-Fi 上报':'STM32 实物采样';
}

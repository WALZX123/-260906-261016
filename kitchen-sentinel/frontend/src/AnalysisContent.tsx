/** 文件职责：辅助分析结果的中文阅读视图。
 * 功能：按结论、事实依据、可能原因、处理建议和待核查项分段，兼容历史英文术语。
 * 技术栈：React、TypeScript、文本映射；关联报警详情、运行周报月报，不修改存档事实或数值。
 * 编写/修改日期（日志对应）：2026-10-16。所有内容按文本渲染，不执行模型返回内容。 */
const glossary:Record<string,string>={supply_low:'供气演示低值异常',test_scenario:'演练场景',monitoring_enabled:'采样启用状态',local_alarm:'本地报警',gas_threshold:'燃气高值阈值',supply_low_latched:'供气异常锁存',cache_pending:'待补传样本数',cache_dropped:'存档缺口计数',adc_error_count:'采样错误次数',processing_test_failures:'算法自检失败项',control_outputs:'控制输出报告',manual_required:'需要人工处理',backfilled:'离线补传',sensor_fault:'采样故障',control_fault:'控制执行异常',storage_fault:'采样存档缺口',multiple:'复合险情',flame:'火焰',smoke:'烟雾',temperature:'温度',gas:'燃气',offline:'设备离线',recovered:'信号已恢复',active:'触发中',normal:'正常',true:'是',false:'否',null:'未提供',MCU:'单片机',STM32:'单片机',ADC:'模数采集',NTC:'热敏电阻',GPIO:'引脚输出',PWM:'脉宽控制',API:'服务接口',JSON:'结构化数据',DeepSeek:'模型服务',UTC:'协调世界时',TCP:'网络连接',SWD:'调试通道'};
/** 历史分析仅在展示时翻译已知独立术语，保留存档正文、数值、事件编号和型号。 */
export function readableAnalysis(text:string){return text.replace(/peak_\*_sampling/g,'已标明非演练的采样峰值').replace(/peak_\*/g,'全部存档峰值').replace(/\b[A-Za-z][A-Za-z0-9_]*\b/g,word=>glossary[word]||word).replace(/`/g,'')}
/** 结构化分析的用户可见文本；协议键只在接口内部使用。 */
export interface AdviceText{summary:string;evidence?:string[];hypotheses?:string[];recommendations?:string[];uncertainties?:string[]}
/** 新分析展示短结论与分类依据，旧版只有整段摘要时保留完整正文。 */
export function AnalysisContent({advice}:{advice:AdviceText}){
 const sections=[['evidence','事实依据'],['hypotheses','可能原因'],['recommendations','处理建议'],['uncertainties','仍需核查']] as const;
 const structured=sections.some(([key])=>advice[key]?.length);
 const summary=structured?advice.summary.split('\n\n证据：')[0]:advice.summary;
 return <div className="analysis-reading"><p className="analysis-conclusion">{readableAnalysis(summary)}</p>{structured&&<div className="analysis-reading-sections">{sections.map(([key,title])=>!!advice[key]?.length&&<section key={key}><h4>{title}</h4><ul>{advice[key]?.map((text,i)=><li key={i}>{readableAnalysis(text)}</li>)}</ul></section>)}</div>}</div>;
}

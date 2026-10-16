/* 文件职责：OLED 四行核心看板接口；主要功能：运行状态、四路测量、四类输出与网络指示。
 * 技术栈：C、128×64 单色绘图；模块联动：demo 与 ATK OLED 驱动。
 * 编写/修改日期（日志对应）：2026-09-23、2026-10-15。 */
#ifndef OLED_DASHBOARD_H
#define OLED_DASHBOARD_H
#include <stdint.h>
/* 显示当前一帧；14×14 中文与 6×12 数字分四行常显，待机隐藏旧测量值。
 * 演练有明确标记，风险状态覆盖普通标题；序号和运行时长由 PC 页面负责展示。
 * 输入为 demo 本轮判断及输出快照；通过 ATK OLED 驱动提交变化页，不等待网络。 */
void oled_dashboard(uint8_t gas,uint8_t smoke,int32_t temperature,uint8_t flame,uint8_t enabled,
                    uint8_t arming,uint8_t hazards,uint8_t valve_closed,uint8_t fan,
                    uint8_t buzzer,uint8_t relay,uint8_t wifi,uint8_t injection,
                    uint32_t sequence,uint32_t uptime_ms);
#endif

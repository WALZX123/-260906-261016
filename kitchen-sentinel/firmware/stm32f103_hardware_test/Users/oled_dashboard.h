/* 文件职责：OLED 运行看板接口；主要功能：中文状态、风险条、阀门风机与网络指示。
 * 技术栈：C、128×64 单色绘图；模块联动：demo 与 ATK OLED 驱动。
 * 编写/修改日期（日志对应）：2026-09-23、2026-10-15。 */
#ifndef OLED_DASHBOARD_H
#define OLED_DASHBOARD_H
#include <stdint.h>
/* 显示当前一帧；待机隐藏旧测量值，演练有明确标记，风险状态覆盖普通标题。 */
void oled_dashboard(uint8_t gas, uint8_t smoke, int32_t temperature, uint8_t enabled,
                    uint8_t arming, uint8_t hazards, uint8_t valve_closed,
                    uint8_t fan, uint8_t wifi, uint8_t injection);
#endif

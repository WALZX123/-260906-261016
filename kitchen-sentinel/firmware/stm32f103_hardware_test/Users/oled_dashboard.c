/* 文件职责：现场 OLED 中文运行信息绘制。
 * 主要功能：中文待机/运行/警报、风险进度条、心跳动画、温度估算及阀门风机和无线状态。
 * 技术栈：C、16 像素子集字模、ATK_OLED 显存绘图；模块联动：demo 传入状态，oled_glyphs 提供字形。
 * 编写/修改日期（日志对应）：2026-09-23、2026-10-15。 */
#include "oled_dashboard.h"
#include "oled_glyphs.h"
#include "./BSP/ATK_OLED/atk_oled.h"
#include <stdio.h>
#include <string.h>

/* 功能：只修改矩形显存，整帧完成后才刷新一次，避免多次 I²C 全屏传输拖慢采样和报警。
 * 输入：矩形坐标及亮灭；联动：bar 与看板，替代原厂 fill 的立即刷新行为。
 * 编写/修改日期（日志对应）：2026-10-13、2026-10-15。 */
static void rectangle(uint8_t x1, uint8_t y1, uint8_t x2, uint8_t y2, uint8_t dot)
{
    uint16_t x, y;
    for (x = x1; x <= x2; x++) for (y = y1; y <= y2; y++) atk_oled_draw_point((uint8_t)x, (uint8_t)y, dot);
}

/* 功能：按 UTF-8 三字节匹配项目所用汉字；只绘制明确收录的字形，不依赖 Keil 的源文件显示编码。
 * 输入：像素坐标与中文串；输出：更新显存；联动：字模表与 ATK 点绘图。日期：2026-10-15。 */
static void chinese(uint8_t x, uint8_t y, const char *text)
{
    while (*text && x <= 112u) {
        unsigned int i, row, col;
        for (i = 0; i < OLED_GLYPH_COUNT; i++) {
            if (!memcmp(text, OLED_GLYPHS[i].utf8, 3u)) {
                for (row = 0; row < 16u; row++) for (col = 0; col < 16u; col++)
                    if (OLED_GLYPHS[i].rows[row] & (0x8000u >> col)) atk_oled_draw_point(x + col, y + row, 1u);
                break;
            }
        }
        text += 3; x += 16u;
    }
}

/* 功能：画相对指标长度条，让风险变化直观可见；输入 0～100，最长 28 像素。
 * 模块联动：demo 的相对指标，不代表标定浓度。日期：2026-09-23、2026-10-15。 */
static void bar(uint8_t x, uint8_t y, uint8_t value)
{
    uint8_t width = (uint8_t)(value * 28u / 100u);
    rectangle(x, y, x + 28u, y, 1u);
    if (width) rectangle(x, y + 2u, x + width - 1u, y + 4u, 1u);
}

/* 功能：组织四行中文与数值；待机显示启用提示，警报显示风险类型，底行显示真实输出指令和网络。
 * 输入由 demo 的同一采样快照提供；只刷新显示，不能改变保护输出。日期：2026-10-15。 */
void oled_dashboard(uint8_t gas, uint8_t smoke, int32_t temperature, uint8_t enabled,
                    uint8_t arming, uint8_t hazards, uint8_t valve_closed,
                    uint8_t fan, uint8_t wifi, uint8_t injection)
{
    static uint8_t beat;
    char text[32];
    rectangle(0u, 0u, 127u, 63u, 0u);
    chinese(0, 0, "\xe7\x81\xb6\xe5\xae\x89" /* 灶安 */);
    chinese(40, 0, !enabled ? "\xe5\xbe\x85\xe6\x9c\xba" /* 待机 */ : arming ? "\xe6\xa3\x80\xe6\x9f\xa5" /* 检查 */ : hazards & 2u ? "\xe7\x81\xab\xe8\xad\xa6" /* 火警 */ : hazards ? "\xe6\xb0\x94\xe8\xad\xa6" /* 气警 */ : "\xe8\xbf\x90\xe8\xa1\x8c" /* 运行 */);
    if (injection) chinese(80, 0, "\xe6\xbc\x94\xe7\xbb\x83" /* 演练 */);
    /* 心跳点每帧切换，无需另设测试页面。 */
    if (++beat & 1u) rectangle(122u, 4u, 125u, 7u, 1u);
    if (!enabled) {
        chinese(0, 20, "\xe8\xaf\xb7\xe5\x9c\xa8\xe7\x94\xb5\xe8\x84\x91\xe7\xab\xaf\xe5\x90\xaf\xe7\x94\xa8" /* 请在电脑端启用 */);
        chinese(0, 36, "\xe9\x87\x87\xe6\xa0\xb7\xe5\xb7\xb2\xe6\x9a\x82\xe5\x81\x9c" /* 采样已暂停 */);
    } else {
        snprintf(text, sizeof(text), "G:%3u S:%3u", gas, smoke);
        atk_oled_show_string(0, 18, text, 12);
        bar(78u, 21u, gas); bar(78u, 28u, smoke);
        if (temperature == (int32_t)0x80000000) snprintf(text, sizeof(text), "T:--.- C");
        else snprintf(text, sizeof(text), "T:%ld.%ld C", (long)(temperature / 100), (long)((temperature < 0 ? -temperature : temperature) % 100 / 10));
        atk_oled_show_string(0, 34, text, 12);
        chinese(78, 32, "\xe4\xbc\xb0\xe7\xae\x97" /* 估算 */);
    }
    chinese(0, 48, valve_closed ? "\xe9\x98\x80\xe5\x85\xb3" /* 阀关 */ : "\xe9\x98\x80\xe5\xbc\x80" /* 阀开 */);
    chinese(40, 48, fan ? "\xe9\xa3\x8e\xe5\xbc\x80" /* 风开 */ : "\xe9\xa3\x8e\xe5\x81\x9c" /* 风停 */);
    atk_oled_show_string(82, 50, wifi ? "WiFi+" : "WiFi-", 12);
    atk_oled_refresh_gram();
}

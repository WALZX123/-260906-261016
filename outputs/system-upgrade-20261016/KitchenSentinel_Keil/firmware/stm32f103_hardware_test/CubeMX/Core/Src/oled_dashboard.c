/* 文件职责：OLED四行核心信息看板。
 * 功能：较大中文与数值常显，只保留运行/警情、无线、四项测量和四类输出。
 * 技术栈：C、14×14字模、原厂6×12 ASCII、变化页传输；关联demo实时状态和ATK OLED。
 * 编写/修改日期（日志对应）：2026-09-23、2026-10-13、2026-10-15。 */
#include "oled_dashboard.h"
#include "oled_glyphs.h"
#include "./BSP/ATK_OLED/atk_oled.h"
#include <stdio.h>
#include <string.h>

/* 功能：匹配UTF-8子集，绘制14像素中文；只更新显存，不逐字发送整屏。 */
static void chinese(uint8_t x,uint8_t y,const char *text)
{
    while(*text && x<=114u) {
        uint32_t i,row,col;
        for(i=0;i<OLED_GLYPH_COUNT;i++) if(!memcmp(text,OLED_GLYPHS[i].utf8,3u)) {
            for(row=0;row<14u;row++) for(col=0;col<14u;col++)
                if(OLED_GLYPHS[i].rows[row]&(0x8000u>>col)) atk_oled_draw_point(x+col,y+row,1u);
            break;
        }
        text+=3;x+=14u;
    }
}

/* 功能：四行保留核心现场信息，去除序号、计时、刷新率、长质量标记和风险条以放大文字。
 * 输入仍兼容demo完整状态；序号等诊断留在PC。待机测量显示--，屏幕不熄灭、不轮页。
 * 联动：主循环先保护再显示；整帧绘制后仅发送变化页。日期：2026-10-15。 */
void oled_dashboard(uint8_t gas,uint8_t smoke,int32_t temperature,uint8_t flame,uint8_t enabled,
                    uint8_t arming,uint8_t hazards,uint8_t valve_closed,uint8_t fan,
                    uint8_t buzzer,uint8_t relay,uint8_t wifi,uint8_t injection,
                    uint32_t sequence,uint32_t uptime_ms)
{
    uint32_t x,y;char text[20];
    (void)sequence;(void)uptime_ms;
    for(x=0;x<128u;x++) for(y=0;y<64u;y++) atk_oled_draw_point(x,y,0u);
    chinese(0,0,"\xe7\x81\xb6\xe5\xae\x89" /* 灶安 */);
    chinese(34,0,!enabled?"\xe5\xbe\x85\xe6\x9c\xba" /* 待机 */:arming?"\xe6\xa3\x80\xe6\x9f\xa5" /* 检查 */:hazards&2u?"\xe7\x81\xab\xe8\xad\xa6" /* 火警 */:hazards?"\xe6\xb0\x94\xe8\xad\xa6" /* 气警 */:temperature==(int32_t)0x80000000?"\xe9\x87\x87\xe6\x95\x85" /* 采故 */:"\xe8\xbf\x90\xe8\xa1\x8c" /* 运行 */);
    if(injection) chinese(68,0,"\xe6\xbc\x94" /* 演 */);
    atk_oled_show_string(90,1,wifi?"WiFi+":"WiFi-",12);
    chinese(0,16,"\xe7\x87\x83\xe6\xb0\x94" /* 燃气 */);chinese(64,16,"\xe7\x83\x9f\xe9\x9b\xbe" /* 烟雾 */);
    if(enabled) {snprintf(text,sizeof(text),"%3u",gas);atk_oled_show_string(30,17,text,12);
        snprintf(text,sizeof(text),"%3u",smoke);atk_oled_show_string(94,17,text,12);}
    else {atk_oled_show_string(30,17," --",12);atk_oled_show_string(94,17," --",12);}
    chinese(0,32,"\xe6\xb8\xa9\xe5\xba\xa6" /* 温度 */);chinese(82,32,"\xe7\x81\xab\xe7\x84\xb0" /* 火焰 */);
    if(enabled && temperature!=(int32_t)0x80000000) {
        uint32_t n=(uint32_t)(temperature<0?-temperature:temperature);
        snprintf(text,sizeof(text),"%s%lu.%luC",temperature<0?"-":"",(unsigned long)(n/100u),(unsigned long)(n%100u/10u));
        atk_oled_show_string(30,33,text,12);
    } else atk_oled_show_string(30,33,"--.-C",12);
    atk_oled_show_string(114,33,enabled?(flame?"1":"0"):"-",12);
    chinese(0,48,valve_closed?"\xe9\x98\x80\xe5\x85\xb3" /* 阀关 */:"\xe9\x98\x80\xe5\xbc\x80" /* 阀开 */);chinese(32,48,fan?"\xe9\xa3\x8e\xe5\xbc\x80" /* 风开 */:"\xe9\xa3\x8e\xe5\x81\x9c" /* 风停 */);
    chinese(64,48,buzzer?"\xe9\xb8\xa3\xe5\xbc\x80" /* 鸣开 */:"\xe9\xb8\xa3\xe5\x81\x9c" /* 鸣停 */);chinese(96,48,relay?"\xe7\x94\xb5\xe5\xbc\x80" /* 电开 */:"\xe7\x94\xb5\xe5\x81\x9c" /* 电停 */);
    atk_oled_refresh_changed();
}

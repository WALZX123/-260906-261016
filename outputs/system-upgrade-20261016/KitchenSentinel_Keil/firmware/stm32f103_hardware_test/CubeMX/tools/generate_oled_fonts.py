"""文件职责：生成OLED核心信息的14像素中文字模。
主要功能：采用本机宋体生成固定子集；技术栈：Pillow、C常量；关联oled_dashboard。
编写/修改日期（日志对应）：2026-09-23、2026-10-15。
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate():
    """每字按字形边界居中，14×14留出行间距；仅生成界面实际使用的汉字。"""
    chars=''.join(dict.fromkeys('灶安待机运行检查火警气采故演燃烟雾温度焰阀关开风停鸣电'))
    font=ImageFont.truetype('C:/Windows/Fonts/simsun.ttc',14)
    lines=['/* 文件职责：OLED14像素中文子集字模；技术栈：C常量；关联oled_dashboard。',
           ' * 编写/修改日期（日志对应）：2026-09-23、2026-10-15。 */',
           '#ifndef OLED_GLYPHS_H','#define OLED_GLYPHS_H','#include <stdint.h>',
           '/* 固定UTF-8键和14行点阵；原厂ASCII字体保持原版权和定义。 */',
           'typedef struct { const char *utf8; uint16_t rows[14]; } OledGlyph;',
           'static const OledGlyph OLED_GLYPHS[] = {']
    for ch in chars:
        tile=Image.new('L',(14,14))
        draw=ImageDraw.Draw(tile)
        box=draw.textbbox((0,0),ch,font=font)
        draw.text(((14-box[2]+box[0])//2-box[0],(14-box[3]+box[1])//2-box[1]),ch,font=font,fill=255)
        rows=[sum(0x8000>>x for x in range(14) if tile.getpixel((x,y))>110) for y in range(14)]
        lines.append('    {"'+''.join('\\x%02x'%b for b in ch.encode())+'", {'+', '.join('0x%04x'%v for v in rows)+'}}, /* '+ch+' */')
    lines+=['};','#define OLED_GLYPH_COUNT (sizeof(OLED_GLYPHS)/sizeof(OLED_GLYPHS[0]))','#endif','']
    (Path(__file__).resolve().parents[1]/'Core/Inc/oled_glyphs.h').write_text('\n'.join(lines),encoding='utf-8-sig')


if __name__=='__main__':
    generate()

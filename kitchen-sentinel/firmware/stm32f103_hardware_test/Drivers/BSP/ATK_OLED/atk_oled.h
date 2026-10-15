/*
 * 文件职责：OLED 图形显示。
 * 主要功能：初始化屏幕、操作显存及绘制文字图形。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：demo.display_update 组织采样和状态，刷新 OLED 显存。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
 ****************************************************************************************************
 * @file        atk_oled.h
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2024-11-28
 * @brief       OLED 驱动代码
 * @license     Copyright (c) 2020-2032, 广州市星翼电子科技有限公司
 ****************************************************************************************************
 * @attention
 *
 * 实验平台:正点原子 M48Z-M3最小系统板STM32F103版
 * 在线视频:www.yuanzige.com
 * 技术论坛:www.openedv.com
 * 公司网址:www.alientek.com
 * 购买地址:openedv.taobao.com
 *
 * 修改说明
 * V1.0 20241101
 * 第一次发布
 *
 ****************************************************************************************************
 */
 
#ifndef __OLED_H
#define __OLED_H

#include "stdlib.h" 
#include "./SYSTEM/sys/sys.h"


/* 命令/数据 定义 */
#define OLED_CMD        0       /* 写命令 */
#define OLED_DATA       1       /* 写数据 */

#define OLED_I2C_ADDR   (0x78)  /* OLED的设备地址 */
/******************************************************************************************/
    
/* 接口说明：atk_oled_wr_byte —— 执行本模块接口操作OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
static void atk_oled_wr_byte(uint8_t data, uint8_t cmd);    /* 写一个字节到OLED */
/* 接口说明：atk_oled_pow —— 执行本模块接口操作OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
static uint32_t atk_oled_pow(uint8_t m, uint8_t n);         /* OLED求平方函数 */


/* 接口说明：atk_oled_init —— 初始化OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_init(void);           /* OLED初始化 */
/* 接口说明：atk_oled_clear —— 清除OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_clear(void);          /* OLED清屏 */
/* 接口说明：atk_oled_display_on —— 执行本模块接口操作OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_display_on(void);     /* 开启OLED显示 */
/* 接口说明：atk_oled_display_off —— 执行本模块接口操作OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_display_off(void);    /* 关闭OLED显示 */
/* 接口说明：atk_oled_refresh_gram —— 刷新OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_refresh_gram(void);   /* 更新显存到OLED */ 
/* 接口说明：atk_oled_draw_point —— 绘制OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_draw_point(uint8_t x, uint8_t y, uint8_t dot);    /* OLED画点 */
/* 接口说明：atk_oled_fill —— 执行本模块接口操作OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_fill(uint8_t x1, uint8_t y1, uint8_t x2, uint8_t y2, uint8_t dot);        /* OLED区域填充 */
/* 接口说明：atk_oled_show_char —— 显示OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_show_char(uint8_t x, uint8_t y, uint8_t chr, uint8_t size, uint8_t mode); /* OLED显示字符 */
/* 接口说明：atk_oled_show_num —— 显示OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_show_num(uint8_t x, uint8_t y, uint32_t num, uint8_t len, uint8_t size);  /* OLED显示数字 */
/* 接口说明：atk_oled_show_string —— 显示OLED 图形显示相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void atk_oled_show_string(uint8_t x, uint8_t y, const char *p, uint8_t size);           /* OLED显示字符串 */
#endif





/*
 * 文件职责：原厂 LED 驱动。
 * 主要功能：提供原厂 LED 引脚初始化和状态接口。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：仅保留原厂参考接口，本项目 PA8 用于风扇，不调用 LED 初始化。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
 ****************************************************************************************************
 * @file        led.h
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2023-08-01
 * @brief       LED 驱动代码
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
 ****************************************************************************************************
 */


#ifndef _LED_H
#define _LED_H
#include "./SYSTEM/sys/sys.h"


/******************************************************************************************/
/* 引脚 定义 */

#define LED0_GPIO_PORT                  GPIOA
#define LED0_GPIO_PIN                   GPIO_PIN_8
#define LED0_GPIO_CLK_ENABLE()          do{ __HAL_RCC_GPIOA_CLK_ENABLE(); }while(0)             /* PA口时钟使能 */

/******************************************************************************************/
/* LED端口定义 */
#define LED0(x)   do{ x ? \
                      HAL_GPIO_WritePin(LED0_GPIO_PORT, LED0_GPIO_PIN, GPIO_PIN_SET) : \
                      HAL_GPIO_WritePin(LED0_GPIO_PORT, LED0_GPIO_PIN, GPIO_PIN_RESET); \
                  }while(0)      /* LED0翻转 */

/* LED取反定义 */
#define LED0_TOGGLE()   do{ HAL_GPIO_TogglePin(LED0_GPIO_PORT, LED0_GPIO_PIN); }while(0)        /* 翻转LED0 */

/******************************************************************************************/
/* 外部接口函数*/
/* 接口说明：led_init —— 初始化原厂 LED 驱动相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void led_init(void);                                                                            /* 初始化 */

#endif

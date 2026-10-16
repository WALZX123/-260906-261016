/*
 * 文件职责：原厂按键驱动。
 * 主要功能：提供原厂按键扫描接口。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：仅保留原厂参考接口，本项目 PA0 用于烟雾，不调用按键初始化。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
 ****************************************************************************************************
 * @file        key.c
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2023-08-01
 * @brief       按键输入 驱动代码
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

#include "./BSP/KEY/key.h"
#include "./SYSTEM/delay/delay.h"


/**
 * @brief       按键初始化函数
 * @param       无
 * @retval      无
 */
/* 接口说明：key_init —— 初始化原厂按键驱动相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void key_init(void)
{
    GPIO_InitTypeDef gpio_init_struct;
    KEY0_GPIO_CLK_ENABLE();                                     /* KEY0时钟使能 */
    WKUP_GPIO_CLK_ENABLE();                                     /* WKUP时钟使能 */

    gpio_init_struct.Pin = KEY0_GPIO_PIN;                       /* KEY0引脚 */
    gpio_init_struct.Mode = GPIO_MODE_INPUT;                    /* 输入 */
    gpio_init_struct.Pull = GPIO_PULLUP;                        /* 上拉 */
    gpio_init_struct.Speed = GPIO_SPEED_FREQ_HIGH;              /* 高速 */
    HAL_GPIO_Init(KEY0_GPIO_PORT, &gpio_init_struct);           /* KEY0引脚模式设置,上拉输入 */

    gpio_init_struct.Pin = WKUP_GPIO_PIN;                       /* WKUP引脚 */
    gpio_init_struct.Mode = GPIO_MODE_INPUT;                    /* 输入 */
    gpio_init_struct.Pull = GPIO_PULLDOWN;                      /* 下拉 */
    gpio_init_struct.Speed = GPIO_SPEED_FREQ_HIGH;              /* 高速 */
    HAL_GPIO_Init(WKUP_GPIO_PORT, &gpio_init_struct);           /* WKUP引脚模式设置,下拉输入 */

}

/**
 * @brief       按键扫描函数
 * @note        该函数有响应优先级(同时按下多个按键): WK_UP > KEY0
 * @param       mode:0 / 1,具体含义如下:
 *   @arg       0,  不支持连续按(当按键按下不放时, 只有第一次调用会返回键值,
 *                  必须松开以后, 再次按下才会返回其他键值)
 *   @arg       1,  支持连续按(当按键按下不放时, 每次调用该函数都会返回键值)
 * @retval      键值,定义如下:
 *              KEY0_PRES, 1, KEY0按下
 *              WKUP_PRES, 2, WK_UP按下
 */
/* 接口说明：key_scan —— 执行本模块接口操作原厂按键驱动相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
uint8_t key_scan(uint8_t mode)
{
    static uint8_t key_up = 1;                          /* 按键松开标志 */
    uint8_t key_val = 0;
    
    if (mode == 1)                                      /* 支持连按 */
    {
        key_up = 1;
    }
    
    if ((key_up == 1) && ((KEY0 == 1) || (WK_UP == 1))) /* 按键松开标志为1，且有按键按下 */
    {
        key_up = 0;
        delay_ms(10);                                   /* 去抖动 */
        if (KEY0 == 1)
        {
            key_val = KEY0_PRES;
        }
        if (WK_UP == 1)
        {
            key_val = WKUP_PRES;
        }
    }
    else if ((KEY0 == 0) && (WK_UP == 0))               /* 没有按键按下，标记按键松开 */
    {
        key_up = 1;
    }
    
    return key_val;                                     /* 返回键值 */
}

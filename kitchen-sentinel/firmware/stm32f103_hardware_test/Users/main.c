/*
 * 文件职责：STM32 上电入口。
 * 主要功能：初始化 HAL、72 MHz 时钟、延时和调试串口，进入厨房采集主循环。
 * 技术栈：C、STM32F103、STM32 HAL、CMSIS、USART1。
 * 模块联动：调用 SYSTEM 时钟与延时驱动，再进入 demo_run；参考 LED/KEY 初始化不再占用 ADC 和风机引脚。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
/**
 ******************************************************************************
 * @file     main.c
 * @author   正点原子团队(ALIENTEK)
 * @version  V1.0
 * @date     2024-11-28
 * @brief    ATK-MB026模块TCP透传实验
 * @license  Copyright (c) 2020-2032, 广州市星翼电子科技有限公司
 ******************************************************************************
 * @attention
 * 
 * 实验平台:正点原子 M48Z-M3最小系统板STM32F103版
 * 在线视频:www.yuanzige.com
 * 技术论坛:www.openedv.com
 * 公司网址:www.alientek.com
 * 购买地址:openedv.taobao.com
 ******************************************************************************
 */

#include "./SYSTEM/sys/sys.h"
#include "./SYSTEM/usart/usart.h"
#include "./SYSTEM/delay/delay.h"
#include "./BSP/LED/led.h"
#include "./BSP/KEY/key.h"
#include "./BSP/ATK_OLED/atk_oled.h"
#include "demo.h"


/**
 * @brief       显示实验信息
 * @param       无
 * @retval      无
 */
/* 功能：保留原厂串口与 OLED 演示信息函数；当前厨房主循环不调用它，避免把演示文字误认作实物状态。
 * 输入/输出：无参数；仅在显式调用时刷新原厂说明，不返回采样。
 * 模块联动：ATK_OLED 与 USART1 原厂演示。
 * 编写/修改日期（日志对应）：2026-09-23。
 */
void show_mesg(void)
{
    /* OLED显示实验信息 */
    atk_oled_show_string(0, 0, "STM32", 12);
    atk_oled_show_string(50, 0, "ATK-MB026", 12);
    atk_oled_show_string(0, 15, "KEY0:test key", 12);
    atk_oled_show_string(0, 30, "WKUP:unvarnished", 12);
    atk_oled_refresh_gram();                /* 更新显示到OLED */
    
    /* 串口输出实验信息 */
    printf("\n");
    printf("********************************\r\n");
    printf("STM32\r\n");
    printf("ATK-MB026\r\n");
    printf("ATOM@ALIENTEK\r\n");
    printf("KEY0: test key\r\n");
    printf("WKUP: unvarnished\r\n");
    printf("********************************\r\n");
    printf("\r\n");
}

/* 功能：初始化 HAL、72 MHz 系统时钟、延时和 115200 串口，再进入持续采样程序。
 * 输入/输出：无参数；demo_run 正常运行时不返回。
 * 模块联动：SYSTEM 时钟和串口驱动 → demo_run → 传感器与保护策略。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
int main(void)
{
    /* 日志对应：2026-09-21 多传感器采集。统一初始化 72 MHz 时钟和 115200 串口。 */
    HAL_Init();                             /* 初始化HAL库 */
    sys_stm32_clock_init(RCC_PLL_MUL9);     /* 设置时钟, 72Mhz */
    delay_init(72);                         /* 延时初始化 */
    usart_init(115200);                     /* 串口初始化为115200 */
    /* 日志对应：2026-09-24 报警联动。PA8 用作风机、PA0 用作 ADC，不能再初始化参考 LED/KEY。 */
    demo_run();                             /* 进入本项目采集与联动循环 */
}

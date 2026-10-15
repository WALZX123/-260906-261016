/*
 * 文件职责：软件 I2C 总线。
 * 主要功能：通过 GPIO 产生 SCL/SDA 时序和应答。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：OLED 使用 PA2/PA3 的软件 I2C，总线读写供屏幕驱动调用。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
 ****************************************************************************************************
 * @file        myiic.h
 * @author      正点原子团队(ALIENTEK)
 * @version     V1.0
 * @date        2020-04-24
 * @brief       IIC 驱动代码
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
 * V1.0 20200424
 * 第一次发布
 *
 ****************************************************************************************************
 */
 
#ifndef __MYIIC_H
#define __MYIIC_H

#include "./SYSTEM/sys/sys.h"


/******************************************************************************************/
/* 引脚 定义 */

#define IIC_SCL_GPIO_PORT               GPIOA
#define IIC_SCL_GPIO_PIN                GPIO_PIN_2
#define IIC_SCL_GPIO_CLK_ENABLE()       do{ __HAL_RCC_GPIOA_CLK_ENABLE(); }while(0)   /* PA口时钟使能 */

#define IIC_SDA_GPIO_PORT               GPIOA
#define IIC_SDA_GPIO_PIN                GPIO_PIN_3
#define IIC_SDA_GPIO_CLK_ENABLE()       do{ __HAL_RCC_GPIOA_CLK_ENABLE(); }while(0)   /* PA口时钟使能 */

/******************************************************************************************/

/* IO操作 */
#define IIC_SCL(x)        do{ x ? \
                              HAL_GPIO_WritePin(IIC_SCL_GPIO_PORT, IIC_SCL_GPIO_PIN, GPIO_PIN_SET) : \
                              HAL_GPIO_WritePin(IIC_SCL_GPIO_PORT, IIC_SCL_GPIO_PIN, GPIO_PIN_RESET); \
                          }while(0)       /* SCL */

#define IIC_SDA(x)        do{ x ? \
                              HAL_GPIO_WritePin(IIC_SDA_GPIO_PORT, IIC_SDA_GPIO_PIN, GPIO_PIN_SET) : \
                              HAL_GPIO_WritePin(IIC_SDA_GPIO_PORT, IIC_SDA_GPIO_PIN, GPIO_PIN_RESET); \
                          }while(0)       /* SDA */

#define IIC_READ_SDA     HAL_GPIO_ReadPin(IIC_SDA_GPIO_PORT, IIC_SDA_GPIO_PIN) /* 读取SDA */


/* IIC所有操作函数 */
/* 接口说明：iic_init —— 初始化软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void iic_init(void);            /* 初始化IIC的IO口 */
/* 接口说明：iic_start —— 启动软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void iic_start(void);           /* 发送IIC开始信号 */
/* 接口说明：iic_stop —— 停止软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void iic_stop(void);            /* 发送IIC停止信号 */
/* 接口说明：iic_ack —— 执行本模块接口操作软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void iic_ack(void);             /* IIC发送ACK信号 */
/* 接口说明：iic_nack —— 执行本模块接口操作软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void iic_nack(void);            /* IIC不发送ACK信号 */
/* 接口说明：iic_wait_ack —— 等待软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
uint8_t iic_wait_ack(void);     /* IIC等待ACK信号 */
/* 接口说明：iic_send_byte —— 发送软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void iic_send_byte(uint8_t txd);/* IIC发送一个字节 */
/* 接口说明：iic_read_byte —— 读取软件 I2C 总线相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
uint8_t iic_read_byte(unsigned char ack);/* IIC读取一个字节 */

#endif


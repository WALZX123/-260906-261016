/*
 * 文件职责：系统时钟及底层支持。
 * 主要功能：配置主频、底层内核操作及必要系统接口。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：main 初始化系统，HAL 和 BSP 依赖底层时钟。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
  ******************************************************************************
  * @file    system_stm32f10x.h
  * @author  MCD Application Team
  * @version V3.5.0
  * @date    11-March-2011
  * @brief   CMSIS Cortex-M3 Device Peripheral Access Layer System Header File.
  ******************************************************************************
  * @attention
  *
  * THE PRESENT FIRMWARE WHICH IS FOR GUIDANCE ONLY AIMS AT PROVIDING CUSTOMERS
  * WITH CODING INFORMATION REGARDING THEIR PRODUCTS IN ORDER FOR THEM TO SAVE
  * TIME. AS A RESULT, STMICROELECTRONICS SHALL NOT BE HELD LIABLE FOR ANY
  * DIRECT, INDIRECT OR CONSEQUENTIAL DAMAGES WITH RESPECT TO ANY CLAIMS ARISING
  * FROM THE CONTENT OF SUCH FIRMWARE AND/OR THE USE MADE BY CUSTOMERS OF THE
  * CODING INFORMATION CONTAINED HEREIN IN CONNECTION WITH THEIR PRODUCTS.
  *
  * <h2><center>&copy; COPYRIGHT 2011 STMicroelectronics</center></h2>
  ******************************************************************************
  */

/** @addtogroup CMSIS
  * @{
  */

/** @addtogroup stm32f10x_system
  * @{
  */  
  
/**
  * @brief Define to prevent recursive inclusion
  */
#ifndef __SYSTEM_STM32F10X_H
#define __SYSTEM_STM32F10X_H

#ifdef __cplusplus
 extern "C" {
#endif 

/** @addtogroup STM32F10x_System_Includes
  * @{
  */

/**
  * @}
  */


/** @addtogroup STM32F10x_System_Exported_types
  * @{
  */

extern uint32_t SystemCoreClock;          /*!< System Clock Frequency (Core Clock) */

/**
  * @}
  */

/** @addtogroup STM32F10x_System_Exported_Constants
  * @{
  */

/**
  * @}
  */

/** @addtogroup STM32F10x_System_Exported_Macros
  * @{
  */

/**
  * @}
  */

/** @addtogroup STM32F10x_System_Exported_Functions
  * @{
  */
  
/* 接口说明：SystemInit —— 初始化芯片系统和向量表状态，由启动汇编在进入 main 前调用。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
extern void SystemInit(void);
/* 接口说明：SystemCoreClockUpdate —— 依据时钟寄存器重新计算 SystemCoreClock，供延时和外设定时使用。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
extern void SystemCoreClockUpdate(void);
/**
  * @}
  */

#ifdef __cplusplus
}
#endif

#endif /*__SYSTEM_STM32F10X_H */

/**
  * @}
  */
  
/**
  * @}
  */  
/******************* (C) COPYRIGHT 2011 STMicroelectronics *****END OF FILE****/

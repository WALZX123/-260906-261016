/*
 * 文件职责：系统异常处理函数声明。
 * 主要功能：声明 Cortex-M3 故障、系统调用和 SysTick 入口，供启动向量与中断实现对应。
 * 技术栈：C 头文件、CMSIS 中断约定、函数声明。
 * 模块联动：与 stm32f1xx_it.c 和启动文件对应；保留 ST 原始版权，不在此文件实现传感器业务。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
/**
  ******************************************************************************
  * @file    Templates/Inc/stm32f1xx_it.h
  * @author  MCD Application Team
  * @brief   This file contains the headers of the interrupt handlers.
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; Copyright (c) 2016 STMicroelectronics.
  * All rights reserved.</center></h2>
  *
  * This software component is licensed by ST under BSD 3-Clause license,
  * the "License"; You may not use this file except in compliance with the
  * License. You may obtain a copy of the License at:
  *                        opensource.org/licenses/BSD-3-Clause
  *
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __STM32F1xx_IT_H
#define __STM32F1xx_IT_H

#ifdef __cplusplus
 extern "C" {
#endif 

/* Includes ------------------------------------------------------------------*/
/* Exported types ------------------------------------------------------------*/
/* Exported constants --------------------------------------------------------*/
/* Exported macro ------------------------------------------------------------*/
/* Exported functions ------------------------------------------------------- */

/* 功能：保留不可屏蔽中断入口，当前沿用空处理模板，不执行采集或保护状态变更。
 * 输入/输出：由处理器向量调用，无普通参数和返回数据。
 * 模块联动：CMSIS 启动向量与 ST 异常模板。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
void NMI_Handler(void);
/* 功能：严重内核故障时停在模板循环，保留故障现场供调试器读取。
 * 输入/输出：由处理器异常调用，不在这里清除故障寄存器或继续采样。
 * 模块联动：CMSIS 故障向量；hardware_test 读取 CFSR/HFSR 辅助定位。
 * 编写/修改日期（日志对应）：2026-09-26。
 */
void HardFault_Handler(void);
/* 功能：内存管理异常时保留现场并停留在模板循环，避免带错误状态继续业务。
 * 输入/输出：处理器异常入口，无普通输入输出。
 * 模块联动：CMSIS 内核异常与 SWD 故障诊断。
 * 编写/修改日期（日志对应）：2026-09-26。
 */
void MemManage_Handler(void);
/* 功能：总线访问异常时保留现场并停留在模板循环，便于检查非法外设或存储访问。
 * 输入/输出：处理器异常入口，无普通输入输出。
 * 模块联动：CMSIS 内核异常与 SWD 故障诊断。
 * 编写/修改日期（日志对应）：2026-09-26。
 */
void BusFault_Handler(void);
/* 功能：指令或处理器使用异常时停留在模板循环，保留内核诊断状态。
 * 输入/输出：处理器异常入口，无普通输入输出。
 * 模块联动：CMSIS 内核异常与 SWD 故障诊断。
 * 编写/修改日期（日志对应）：2026-09-26。
 */
void UsageFault_Handler(void);
/* 功能：保留系统调用异常入口，当前工程没有在此实现额外调度逻辑。
 * 输入/输出：由内核向量调用，无普通参数和返回值。
 * 模块联动：CMSIS 与 ST 标准中断模板。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
void SVC_Handler(void);
/* 功能：保留调试监控异常入口，当前沿用模板空处理。
 * 输入/输出：由内核调试异常调用，不在此改变传感器或执行器状态。
 * 模块联动：CMSIS 与调试监控向量。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
void DebugMon_Handler(void);
/* 功能：保留可挂起系统服务入口，当前主循环未在此执行任务切换。
 * 输入/输出：由内核向量调用，无普通输入输出。
 * 模块联动：CMSIS 与 ST 标准中断模板。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
void PendSV_Handler(void);
/* 功能：更新 HAL 毫秒计数，为采样周期、ADC 等待和超时判断提供时间基准。
 * 输入/输出：由 SysTick 周期调用，无普通参数和返回值。
 * 模块联动：HAL_IncTick → HAL_GetTick、delay、ADC 超时与状态运行时间。
 * 编写/修改日期（日志对应）：2026-09-21。
 */
void SysTick_Handler(void);

#ifdef __cplusplus
}
#endif

#endif /* __STM32F1xx_IT_H */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/

/*
 * 文件职责：GPIO 外设。
 * 主要功能：配置输入输出、复用模式和电平读写。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：demo 采样 DO、保护输出，IIC 与串口引脚初始化。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
  ******************************************************************************
  * @file    stm32f1xx_hal_gpio_ex.c
  * @author  MCD Application Team
  * @brief   GPIO Extension HAL module driver.
  *         This file provides firmware functions to manage the following
  *          functionalities of the General Purpose Input/Output (GPIO) extension peripheral.
  *           + Extended features functions
  *
  @verbatim
  ==============================================================================
                    ##### GPIO Peripheral extension features #####
  ==============================================================================
  [..] GPIO module on STM32F1 family, manage also the AFIO register:
       (+) Possibility to use the EVENTOUT Cortex feature

                     ##### How to use this driver #####
  ==============================================================================
  [..] This driver provides functions to use EVENTOUT Cortex feature
    (#) Configure EVENTOUT Cortex feature using the function HAL_GPIOEx_ConfigEventout()
    (#) Activate EVENTOUT Cortex feature using the HAL_GPIOEx_EnableEventout()
    (#) Deactivate EVENTOUT Cortex feature using the HAL_GPIOEx_DisableEventout()

  @endverbatim
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

/* Includes ------------------------------------------------------------------*/
#include "stm32f1xx_hal.h"

/** @addtogroup STM32F1xx_HAL_Driver
  * @{
  */

/** @defgroup GPIOEx GPIOEx
  * @brief GPIO HAL module driver
  * @{
  */

#ifdef HAL_GPIO_MODULE_ENABLED

/** @defgroup GPIOEx_Exported_Functions GPIOEx Exported Functions
  * @{
  */

/** @defgroup GPIOEx_Exported_Functions_Group1 Extended features functions
 *  @brief    Extended features functions
 *
@verbatim
  ==============================================================================
                 ##### Extended features functions #####
  ==============================================================================
    [..]  This section provides functions allowing to:
    (+) Configure EVENTOUT Cortex feature using the function HAL_GPIOEx_ConfigEventout()
    (+) Activate EVENTOUT Cortex feature using the HAL_GPIOEx_EnableEventout()
    (+) Deactivate EVENTOUT Cortex feature using the HAL_GPIOEx_DisableEventout()

@endverbatim
  * @{
  */

/**
  * @brief  Configures the port and pin on which the EVENTOUT Cortex signal will be connected.
  * @param  GPIO_PortSource Select the port used to output the Cortex EVENTOUT signal.
  *   This parameter can be a value of @ref GPIOEx_EVENTOUT_PORT.
  * @param  GPIO_PinSource Select the pin used to output the Cortex EVENTOUT signal.
  *   This parameter can be a value of @ref GPIOEx_EVENTOUT_PIN.
  * @retval None
  */
/* 接口说明：HAL_GPIOEx_ConfigEventout —— 配置GPIO 外设相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_GPIOEx_ConfigEventout(uint32_t GPIO_PortSource, uint32_t GPIO_PinSource)
{
  /* Verify the parameters */
  assert_param(IS_AFIO_EVENTOUT_PORT(GPIO_PortSource));
  assert_param(IS_AFIO_EVENTOUT_PIN(GPIO_PinSource));

  /* Apply the new configuration */
  MODIFY_REG(AFIO->EVCR, (AFIO_EVCR_PORT) | (AFIO_EVCR_PIN), (GPIO_PortSource) | (GPIO_PinSource));
}

/**
  * @brief  Enables the Event Output.
  * @retval None
  */
/* 接口说明：HAL_GPIOEx_EnableEventout —— 使能GPIO 外设相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_GPIOEx_EnableEventout(void)
{
  SET_BIT(AFIO->EVCR, AFIO_EVCR_EVOE);
}

/**
  * @brief  Disables the Event Output.
  * @retval None
  */
/* 接口说明：HAL_GPIOEx_DisableEventout —— 禁用GPIO 外设相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_GPIOEx_DisableEventout(void)
{
  CLEAR_BIT(AFIO->EVCR, AFIO_EVCR_EVOE);
}

/**
  * @}
  */

/**
  * @}
  */

#endif /* HAL_GPIO_MODULE_ENABLED */

/**
  * @}
  */

/**
  * @}
  */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/

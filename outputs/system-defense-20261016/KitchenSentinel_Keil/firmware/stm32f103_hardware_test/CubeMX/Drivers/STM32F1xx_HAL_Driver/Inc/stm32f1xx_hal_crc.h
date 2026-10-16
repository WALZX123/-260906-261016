/*
 * 文件职责：STM32 外设库接口。
 * 主要功能：定义本系列外设寄存器、类型、常量和驱动接口。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：stm32f1xx_hal_conf 选择外设模块，相关 HAL 源文件实现这些接口。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
  ******************************************************************************
  * @file    stm32f1xx_hal_crc.h
  * @author  MCD Application Team
  * @brief   Header file of CRC HAL module.
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
#ifndef STM32F1xx_HAL_CRC_H
#define STM32F1xx_HAL_CRC_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f1xx_hal_def.h"

/** @addtogroup STM32F1xx_HAL_Driver
  * @{
  */

/** @addtogroup CRC
  * @{
  */

/* Exported types ------------------------------------------------------------*/
/** @defgroup CRC_Exported_Types CRC Exported Types
  * @{
  */

/**
  * @brief  CRC HAL State Structure definition
  */
typedef enum
{
  HAL_CRC_STATE_RESET     = 0x00U,  /*!< CRC not yet initialized or disabled */
  HAL_CRC_STATE_READY     = 0x01U,  /*!< CRC initialized and ready for use   */
  HAL_CRC_STATE_BUSY      = 0x02U,  /*!< CRC internal process is ongoing     */
  HAL_CRC_STATE_TIMEOUT   = 0x03U,  /*!< CRC timeout state                   */
  HAL_CRC_STATE_ERROR     = 0x04U   /*!< CRC error state                     */
} HAL_CRC_StateTypeDef;


/**
  * @brief  CRC Handle Structure definition
  */
typedef struct
{
  CRC_TypeDef                 *Instance;   /*!< Register base address        */

  HAL_LockTypeDef             Lock;        /*!< CRC Locking object           */

  __IO HAL_CRC_StateTypeDef   State;       /*!< CRC communication state      */

} CRC_HandleTypeDef;
/**
  * @}
  */

/* Exported constants --------------------------------------------------------*/
/** @defgroup CRC_Exported_Constants CRC Exported Constants
  * @{
  */

/**
  * @}
  */

/* Exported macros -----------------------------------------------------------*/
/** @defgroup CRC_Exported_Macros CRC Exported Macros
  * @{
  */

/** @brief Reset CRC handle state.
  * @param  __HANDLE__ CRC handle.
  * @retval None
  */
#define __HAL_CRC_RESET_HANDLE_STATE(__HANDLE__) ((__HANDLE__)->State = HAL_CRC_STATE_RESET)

/**
  * @brief  Reset CRC Data Register.
  * @param  __HANDLE__ CRC handle
  * @retval None
  */
#define __HAL_CRC_DR_RESET(__HANDLE__) ((__HANDLE__)->Instance->CR |= CRC_CR_RESET)

/**
  * @brief Store data in the Independent Data (ID) register.
  * @param __HANDLE__ CRC handle
  * @param __VALUE__  Value to be stored in the ID register
  * @note  Refer to the Reference Manual to get the authorized __VALUE__ length in bits
  * @retval None
  */
#define __HAL_CRC_SET_IDR(__HANDLE__, __VALUE__) (WRITE_REG((__HANDLE__)->Instance->IDR, (__VALUE__)))

/**
  * @brief Return the data stored in the Independent Data (ID) register.
  * @param __HANDLE__ CRC handle
  * @note  Refer to the Reference Manual to get the authorized __VALUE__ length in bits
  * @retval Value of the ID register
  */
#define __HAL_CRC_GET_IDR(__HANDLE__) (((__HANDLE__)->Instance->IDR) & CRC_IDR_IDR)
/**
  * @}
  */


/* Private macros --------------------------------------------------------*/
/** @defgroup  CRC_Private_Macros CRC Private Macros
  * @{
  */

/**
  * @}
  */

/* Exported functions --------------------------------------------------------*/
/** @defgroup CRC_Exported_Functions CRC Exported Functions
  * @{
  */

/* Initialization and de-initialization functions  ****************************/
/** @defgroup CRC_Exported_Functions_Group1 Initialization and de-initialization functions
  * @{
  */
/* 接口说明：HAL_CRC_Init —— 初始化STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_CRC_Init(CRC_HandleTypeDef *hcrc);
/* 接口说明：HAL_CRC_DeInit —— 复位并撤销初始化STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_CRC_DeInit(CRC_HandleTypeDef *hcrc);
/* 接口说明：HAL_CRC_MspInit —— 初始化底层外设资源STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_CRC_MspInit(CRC_HandleTypeDef *hcrc);
/* 接口说明：HAL_CRC_MspDeInit —— 释放底层外设资源STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_CRC_MspDeInit(CRC_HandleTypeDef *hcrc);
/**
  * @}
  */

/* Peripheral Control functions ***********************************************/
/** @defgroup CRC_Exported_Functions_Group2 Peripheral Control functions
  * @{
  */
/* 接口说明：HAL_CRC_Accumulate —— 执行本模块接口操作STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
uint32_t HAL_CRC_Accumulate(CRC_HandleTypeDef *hcrc, uint32_t pBuffer[], uint32_t BufferLength);
/* 接口说明：HAL_CRC_Calculate —— 执行本模块接口操作STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
uint32_t HAL_CRC_Calculate(CRC_HandleTypeDef *hcrc, uint32_t pBuffer[], uint32_t BufferLength);
/**
  * @}
  */

/* Peripheral State and Error functions ***************************************/
/** @defgroup CRC_Exported_Functions_Group3 Peripheral State functions
  * @{
  */
/* 接口说明：HAL_CRC_GetState —— 查询状态STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_CRC_StateTypeDef HAL_CRC_GetState(CRC_HandleTypeDef *hcrc);
/**
  * @}
  */

/**
  * @}
  */

/**
  * @}
  */

/**
  * @}
  */

#ifdef __cplusplus
}
#endif

#endif /* STM32F1xx_HAL_CRC_H */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/

/*
 * 文件职责：STM32 外设库接口。
 * 主要功能：定义本系列外设寄存器、类型、常量和驱动接口。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：stm32f1xx_hal_conf 选择外设模块，相关 HAL 源文件实现这些接口。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**
  ******************************************************************************
  * @file    stm32f1xx_hal_sram.h
  * @author  MCD Application Team
  * @brief   Header file of SRAM HAL module.
  ******************************************************************************
  * @attention
  *
  * <h2><center>&copy; Copyright (c) 2016 STMicroelectronics.
  * All rights reserved.</center></h2>
  *
  * This software component is licensed by ST under BSD 3-Clause license,
  * the "License"; You may not use this file except in compliance with the
  * License. You may obtain a copy of the License at:
  *                       opensource.org/licenses/BSD-3-Clause
  *
  ******************************************************************************
  */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef STM32F1xx_HAL_SRAM_H
#define STM32F1xx_HAL_SRAM_H

#ifdef __cplusplus
extern "C" {
#endif

#if defined FSMC_BANK1

/* Includes ------------------------------------------------------------------*/
#include "stm32f1xx_ll_fsmc.h"

/** @addtogroup STM32F1xx_HAL_Driver
  * @{
  */
/** @addtogroup SRAM
  * @{
  */

/* Exported typedef ----------------------------------------------------------*/

/** @defgroup SRAM_Exported_Types SRAM Exported Types
  * @{
  */
/**
  * @brief  HAL SRAM State structures definition
  */
typedef enum
{
  HAL_SRAM_STATE_RESET     = 0x00U,  /*!< SRAM not yet initialized or disabled           */
  HAL_SRAM_STATE_READY     = 0x01U,  /*!< SRAM initialized and ready for use             */
  HAL_SRAM_STATE_BUSY      = 0x02U,  /*!< SRAM internal process is ongoing               */
  HAL_SRAM_STATE_ERROR     = 0x03U,  /*!< SRAM error state                               */
  HAL_SRAM_STATE_PROTECTED = 0x04U   /*!< SRAM peripheral NORSRAM device write protected */

} HAL_SRAM_StateTypeDef;

/**
  * @brief  SRAM handle Structure definition
  */
#if (USE_HAL_SRAM_REGISTER_CALLBACKS == 1)
typedef struct __SRAM_HandleTypeDef
#else
typedef struct
#endif /* USE_HAL_SRAM_REGISTER_CALLBACKS  */
{
  FSMC_NORSRAM_TypeDef           *Instance;  /*!< Register base address                        */

  FSMC_NORSRAM_EXTENDED_TypeDef  *Extended;  /*!< Extended mode register base address          */

  FSMC_NORSRAM_InitTypeDef       Init;       /*!< SRAM device control configuration parameters */

  HAL_LockTypeDef               Lock;       /*!< SRAM locking object                          */

  __IO HAL_SRAM_StateTypeDef    State;      /*!< SRAM device access state                     */

  DMA_HandleTypeDef             *hdma;      /*!< Pointer DMA handler                          */

#if (USE_HAL_SRAM_REGISTER_CALLBACKS == 1)
  void (* MspInitCallback)(struct __SRAM_HandleTypeDef *hsram);               /*!< SRAM Msp Init callback              */
  void (* MspDeInitCallback)(struct __SRAM_HandleTypeDef *hsram);             /*!< SRAM Msp DeInit callback            */
  void (* DmaXferCpltCallback)(DMA_HandleTypeDef *hdma);                      /*!< SRAM DMA Xfer Complete callback     */
  void (* DmaXferErrorCallback)(DMA_HandleTypeDef *hdma);                     /*!< SRAM DMA Xfer Error callback        */
#endif
} SRAM_HandleTypeDef;

#if (USE_HAL_SRAM_REGISTER_CALLBACKS == 1)
/**
  * @brief  HAL SRAM Callback ID enumeration definition
  */
typedef enum
{
  HAL_SRAM_MSP_INIT_CB_ID       = 0x00U,  /*!< SRAM MspInit Callback ID           */
  HAL_SRAM_MSP_DEINIT_CB_ID     = 0x01U,  /*!< SRAM MspDeInit Callback ID         */
  HAL_SRAM_DMA_XFER_CPLT_CB_ID  = 0x02U,  /*!< SRAM DMA Xfer Complete Callback ID */
  HAL_SRAM_DMA_XFER_ERR_CB_ID   = 0x03U   /*!< SRAM DMA Xfer Complete Callback ID */
} HAL_SRAM_CallbackIDTypeDef;

/**
  * @brief  HAL SRAM Callback pointer definition
  */
typedef void (*pSRAM_CallbackTypeDef)(SRAM_HandleTypeDef *hsram);
typedef void (*pSRAM_DmaCallbackTypeDef)(DMA_HandleTypeDef *hdma);
#endif
/**
  * @}
  */

/* Exported constants --------------------------------------------------------*/
/* Exported macro ------------------------------------------------------------*/

/** @defgroup SRAM_Exported_Macros SRAM Exported Macros
  * @{
  */

/** @brief Reset SRAM handle state
  * @param  __HANDLE__ SRAM handle
  * @retval None
  */
#if (USE_HAL_SRAM_REGISTER_CALLBACKS == 1)
#define __HAL_SRAM_RESET_HANDLE_STATE(__HANDLE__)         do {                                             \
                                                               (__HANDLE__)->State = HAL_SRAM_STATE_RESET; \
                                                               (__HANDLE__)->MspInitCallback = NULL;       \
                                                               (__HANDLE__)->MspDeInitCallback = NULL;     \
                                                             } while(0)
#else
#define __HAL_SRAM_RESET_HANDLE_STATE(__HANDLE__) ((__HANDLE__)->State = HAL_SRAM_STATE_RESET)
#endif

/**
  * @}
  */

/* Exported functions --------------------------------------------------------*/
/** @addtogroup SRAM_Exported_Functions SRAM Exported Functions
  * @{
  */

/** @addtogroup SRAM_Exported_Functions_Group1 Initialization and de-initialization functions
  * @{
  */

/* Initialization/de-initialization functions  ********************************/
/* 接口说明：HAL_SRAM_Init —— 初始化STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Init(SRAM_HandleTypeDef *hsram, FSMC_NORSRAM_TimingTypeDef *Timing,
                                FSMC_NORSRAM_TimingTypeDef *ExtTiming);
/* 接口说明：HAL_SRAM_DeInit —— 复位并撤销初始化STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_DeInit(SRAM_HandleTypeDef *hsram);
/* 接口说明：HAL_SRAM_MspInit —— 初始化底层外设资源STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_SRAM_MspInit(SRAM_HandleTypeDef *hsram);
/* 接口说明：HAL_SRAM_MspDeInit —— 释放底层外设资源STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_SRAM_MspDeInit(SRAM_HandleTypeDef *hsram);

/**
  * @}
  */

/** @addtogroup SRAM_Exported_Functions_Group2 Input Output and memory control functions
  * @{
  */

/* I/O operation functions  ***************************************************/
/* 接口说明：HAL_SRAM_Read_8b —— 读取STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Read_8b(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint8_t *pDstBuffer,
                                   uint32_t BufferSize);
/* 接口说明：HAL_SRAM_Write_8b —— 写入STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Write_8b(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint8_t *pSrcBuffer,
                                    uint32_t BufferSize);
/* 接口说明：HAL_SRAM_Read_16b —— 读取STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Read_16b(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint16_t *pDstBuffer,
                                    uint32_t BufferSize);
/* 接口说明：HAL_SRAM_Write_16b —— 写入STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Write_16b(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint16_t *pSrcBuffer,
                                     uint32_t BufferSize);
/* 接口说明：HAL_SRAM_Read_32b —— 读取STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Read_32b(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint32_t *pDstBuffer,
                                    uint32_t BufferSize);
/* 接口说明：HAL_SRAM_Write_32b —— 写入STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Write_32b(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint32_t *pSrcBuffer,
                                     uint32_t BufferSize);
/* 接口说明：HAL_SRAM_Read_DMA —— 读取STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Read_DMA(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint32_t *pDstBuffer,
                                    uint32_t BufferSize);
/* 接口说明：HAL_SRAM_Write_DMA —— 写入STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_Write_DMA(SRAM_HandleTypeDef *hsram, uint32_t *pAddress, uint32_t *pSrcBuffer,
                                     uint32_t BufferSize);

/* 接口说明：HAL_SRAM_DMA_XferCpltCallback —— 处理回调STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_SRAM_DMA_XferCpltCallback(DMA_HandleTypeDef *hdma);
/* 接口说明：HAL_SRAM_DMA_XferErrorCallback —— 处理回调STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
void HAL_SRAM_DMA_XferErrorCallback(DMA_HandleTypeDef *hdma);

#if (USE_HAL_SRAM_REGISTER_CALLBACKS == 1)
/* SRAM callback registering/unregistering */
/* 接口说明：HAL_SRAM_RegisterCallback —— 处理回调STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_RegisterCallback(SRAM_HandleTypeDef *hsram, HAL_SRAM_CallbackIDTypeDef CallbackId,
                                            pSRAM_CallbackTypeDef pCallback);
/* 接口说明：HAL_SRAM_UnRegisterCallback —— 处理回调STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_UnRegisterCallback(SRAM_HandleTypeDef *hsram, HAL_SRAM_CallbackIDTypeDef CallbackId);
/* 接口说明：HAL_SRAM_RegisterDmaCallback —— 处理回调STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_RegisterDmaCallback(SRAM_HandleTypeDef *hsram, HAL_SRAM_CallbackIDTypeDef CallbackId,
                                               pSRAM_DmaCallbackTypeDef pCallback);
#endif

/**
  * @}
  */

/** @addtogroup SRAM_Exported_Functions_Group3 Control functions
  * @{
  */

/* SRAM Control functions  ****************************************************/
/* 接口说明：HAL_SRAM_WriteOperation_Enable —— 使能STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_WriteOperation_Enable(SRAM_HandleTypeDef *hsram);
/* 接口说明：HAL_SRAM_WriteOperation_Disable —— 禁用STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_StatusTypeDef HAL_SRAM_WriteOperation_Disable(SRAM_HandleTypeDef *hsram);

/**
  * @}
  */

/** @addtogroup SRAM_Exported_Functions_Group4 Peripheral State functions
  * @{
  */

/* SRAM  State functions ******************************************************/
/* 接口说明：HAL_SRAM_GetState —— 查询状态STM32 外设库接口相关状态或资源。
 * 参数、返回值与可用调用时机见下方原厂接口文档；项目调用关系见文件头。
 * 编写/修改日期（日志对应）：2026-10-14。 */
HAL_SRAM_StateTypeDef HAL_SRAM_GetState(SRAM_HandleTypeDef *hsram);

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

#endif /* FSMC_BANK1 */

#ifdef __cplusplus
}
#endif

#endif /* STM32F1xx_HAL_SRAM_H */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/

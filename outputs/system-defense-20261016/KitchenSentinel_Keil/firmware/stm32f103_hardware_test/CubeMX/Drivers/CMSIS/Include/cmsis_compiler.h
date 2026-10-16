/*
 * 文件职责：CMSIS 编译器与内核适配。
 * 主要功能：提供 ARMCC 内联汇编、指令屏障和内核类型。
 * 技术栈：C、STM32F103、CMSIS/HAL、ARMCC 5；下方保留原厂版权与接口说明。
 * 模块联动：工程使用 ARMCC 5 和 Cortex-M3，HAL 通过这些接口操作内核。
 * 编写/修改日期（日志对应）：2026-10-14（工程归档和中文说明）。
 */
/**************************************************************************//**
 * @file     cmsis_compiler.h
 * @brief    CMSIS compiler generic header file
 * @version  V5.0.4
 * @date     10. January 2018
 ******************************************************************************/
/*
 * Copyright (c) 2009-2018 Arm Limited. All rights reserved.
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the License); you may
 * not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef __CMSIS_COMPILER_H
#define __CMSIS_COMPILER_H

#include <stdint.h>

/*
 * Arm Compiler 6 (armclang)
 */
#if defined (__ARMCC_VERSION) && (__ARMCC_VERSION >= 6010050)
  #include "cmsis_armclang.h"

/*
 * Arm Compiler 4/5
 */
#elif   defined ( __CC_ARM )
  #include "cmsis_armcc.h"

/*
 * GNU Compiler
 */
#elif defined ( __GNUC__ )
  #include "cmsis_gcc.h"


/*
 * IAR Compiler
 */
#elif defined ( __ICCARM__ )
  #include <cmsis_iccarm.h>


/*
 * TI Arm Compiler
 */
#elif defined ( __TI_ARM__ )
  #include <cmsis_ccs.h>

  #ifndef   __ASM
    #define __ASM                                  __asm
  #endif
  #ifndef   __INLINE
    #define __INLINE                               inline
  #endif
  #ifndef   __STATIC_INLINE
    #define __STATIC_INLINE                        static inline
  #endif
  #ifndef   __STATIC_FORCEINLINE
    #define __STATIC_FORCEINLINE                   __STATIC_INLINE
  #endif
  #ifndef   __NO_RETURN
    #define __NO_RETURN                            __attribute__((noreturn))
  #endif
  #ifndef   __USED
    #define __USED                                 __attribute__((used))
  #endif
  #ifndef   __WEAK
    #define __WEAK                                 __attribute__((weak))
  #endif
  #ifndef   __PACKED
    #define __PACKED                               __attribute__((packed))
  #endif
  #ifndef   __PACKED_STRUCT
    #define __PACKED_STRUCT                        struct __attribute__((packed))
  #endif
  #ifndef   __PACKED_UNION
    #define __PACKED_UNION                         union __attribute__((packed))
  #endif
  #ifndef   __UNALIGNED_UINT32        /* deprecated */
    struct __attribute__((packed)) T_UINT32 { uint32_t v; };
    #define __UNALIGNED_UINT32(x)                  (((struct T_UINT32 *)(x))->v)
  #endif
  #ifndef   __UNALIGNED_UINT16_WRITE
    __PACKED_STRUCT T_UINT16_WRITE { uint16_t v; };
    #define __UNALIGNED_UINT16_WRITE(addr, val)    (void)((((struct T_UINT16_WRITE *)(void*)(addr))->v) = (val))
  #endif
  #ifndef   __UNALIGNED_UINT16_READ
    __PACKED_STRUCT T_UINT16_READ { uint16_t v; };
    #define __UNALIGNED_UINT16_READ(addr)          (((const struct T_UINT16_READ *)(const void *)(addr))->v)
  #endif
  #ifndef   __UNALIGNED_UINT32_WRITE
    __PACKED_STRUCT T_UINT32_WRITE { uint32_t v; };
    #define __UNALIGNED_UINT32_WRITE(addr, val)    (void)((((struct T_UINT32_WRITE *)(void *)(addr))->v) = (val))
  #endif
  #ifndef   __UNALIGNED_UINT32_READ
    __PACKED_STRUCT T_UINT32_READ { uint32_t v; };
    #define __UNALIGNED_UINT32_READ(addr)          (((const struct T_UINT32_READ *)(const void *)(addr))->v)
  #endif
  #ifndef   __ALIGNED
    #define __ALIGNED(x)                           __attribute__((aligned(x)))
  #endif
  #ifndef   __RESTRICT
    #warning No compiler specific solution for __RESTRICT. __RESTRICT is ignored.
    #define __RESTRICT
  #endif


/*
 * TASKING Compiler
 */
#elif defined ( __TASKING__ )
  /*
   * The CMSIS functions have been implemented as intrinsics in the compiler.
   * Please use "carm -?i" to get an up to date list of all intrinsics,
   * Including the CMSIS ones.
   */

  #ifndef   __ASM
    #define __ASM                                  __asm
  #endif
  #ifndef   __INLINE
    #define __INLINE                               inline
  #endif
  #ifndef   __STATIC_INLINE
    #define __STATIC_INLINE                        static inline
  #endif
  #ifndef   __STATIC_FORCEINLINE
    #define __STATIC_FORCEINLINE                   __STATIC_INLINE
  #endif
  #ifndef   __NO_RETURN
    #define __NO_RETURN                            __attribute__((noreturn))
  #endif
  #ifndef   __USED
    #define __USED                                 __attribute__((used))
  #endif
  #ifndef   __WEAK
    #define __WEAK                                 __attribute__((weak))
  #endif
  #ifndef   __PACKED
    #define __PACKED                               __packed__
  #endif
  #ifndef   __PACKED_STRUCT
    #define __PACKED_STRUCT                        struct __packed__
  #endif
  #ifndef   __PACKED_UNION
    #define __PACKED_UNION                         union __packed__
  #endif
  #ifndef   __UNALIGNED_UINT32        /* deprecated */
    struct __packed__ T_UINT32 { uint32_t v; };
    #define __UNALIGNED_UINT32(x)                  (((struct T_UINT32 *)(x))->v)
  #endif
  #ifndef   __UNALIGNED_UINT16_WRITE
    __PACKED_STRUCT T_UINT16_WRITE { uint16_t v; };
    #define __UNALIGNED_UINT16_WRITE(addr, val)    (void)((((struct T_UINT16_WRITE *)(void *)(addr))->v) = (val))
  #endif
  #ifndef   __UNALIGNED_UINT16_READ
    __PACKED_STRUCT T_UINT16_READ { uint16_t v; };
    #define __UNALIGNED_UINT16_READ(addr)          (((const struct T_UINT16_READ *)(const void *)(addr))->v)
  #endif
  #ifndef   __UNALIGNED_UINT32_WRITE
    __PACKED_STRUCT T_UINT32_WRITE { uint32_t v; };
    #define __UNALIGNED_UINT32_WRITE(addr, val)    (void)((((struct T_UINT32_WRITE *)(void *)(addr))->v) = (val))
  #endif
  #ifndef   __UNALIGNED_UINT32_READ
    __PACKED_STRUCT T_UINT32_READ { uint32_t v; };
    #define __UNALIGNED_UINT32_READ(addr)          (((const struct T_UINT32_READ *)(const void *)(addr))->v)
  #endif
  #ifndef   __ALIGNED
    #define __ALIGNED(x)              __align(x)
  #endif
  #ifndef   __RESTRICT
    #warning No compiler specific solution for __RESTRICT. __RESTRICT is ignored.
    #define __RESTRICT
  #endif


/*
 * COSMIC Compiler
 */
#elif defined ( __CSMC__ )
   #include <cmsis_csm.h>

 #ifndef   __ASM
    #define __ASM                                  _asm
  #endif
  #ifndef   __INLINE
    #define __INLINE                               inline
  #endif
  #ifndef   __STATIC_INLINE
    #define __STATIC_INLINE                        static inline
  #endif
  #ifndef   __STATIC_FORCEINLINE
    #define __STATIC_FORCEINLINE                   __STATIC_INLINE
  #endif
  #ifndef   __NO_RETURN
    // NO RETURN is automatically detected hence no warning here
    #define __NO_RETURN
  #endif
  #ifndef   __USED
    #warning No compiler specific solution for __USED. __USED is ignored.
    #define __USED
  #endif
  #ifndef   __WEAK
    #define __WEAK                                 __weak
  #endif
  #ifndef   __PACKED
    #define __PACKED                               @packed
  #endif
  #ifndef   __PACKED_STRUCT
    #define __PACKED_STRUCT                        @packed struct
  #endif
  #ifndef   __PACKED_UNION
    #define __PACKED_UNION                         @packed union
  #endif
  #ifndef   __UNALIGNED_UINT32        /* deprecated */
    @packed struct T_UINT32 { uint32_t v; };
    #define __UNALIGNED_UINT32(x)                  (((struct T_UINT32 *)(x))->v)
  #endif
  #ifndef   __UNALIGNED_UINT16_WRITE
    __PACKED_STRUCT T_UINT16_WRITE { uint16_t v; };
    #define __UNALIGNED_UINT16_WRITE(addr, val)    (void)((((struct T_UINT16_WRITE *)(void *)(addr))->v) = (val))
  #endif
  #ifndef   __UNALIGNED_UINT16_READ
    __PACKED_STRUCT T_UINT16_READ { uint16_t v; };
    #define __UNALIGNED_UINT16_READ(addr)          (((const struct T_UINT16_READ *)(const void *)(addr))->v)
  #endif
  #ifndef   __UNALIGNED_UINT32_WRITE
    __PACKED_STRUCT T_UINT32_WRITE { uint32_t v; };
    #define __UNALIGNED_UINT32_WRITE(addr, val)    (void)((((struct T_UINT32_WRITE *)(void *)(addr))->v) = (val))
  #endif
  #ifndef   __UNALIGNED_UINT32_READ
    __PACKED_STRUCT T_UINT32_READ { uint32_t v; };
    #define __UNALIGNED_UINT32_READ(addr)          (((const struct T_UINT32_READ *)(const void *)(addr))->v)
  #endif
  #ifndef   __ALIGNED
    #warning No compiler specific solution for __ALIGNED. __ALIGNED is ignored.
    #define __ALIGNED(x)
  #endif
  #ifndef   __RESTRICT
    #warning No compiler specific solution for __RESTRICT. __RESTRICT is ignored.
    #define __RESTRICT
  #endif


#else
  #error Unknown compiler.
#endif


#endif /* __CMSIS_COMPILER_H */


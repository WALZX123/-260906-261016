/*
 * 文件职责：固件与电脑之间的 SWD 状态协议。
 * 主要功能：定义状态签名、版本、采样、滤波、输出寄存器、自测及危险类型字段。
 * 技术栈：C volatile 状态块、32 位字段、一致快照奇偶计数。
 * 模块联动：demo.c 更新 g_hardware_status，hardware_test 按 MAP 地址与版本读取，gateway.swd 转为设备遥测；字段顺序关系到协议兼容。
 * 编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-09-21、2026-09-22、2026-09-24；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
 */
#ifndef KITCHEN_HARDWARE_STATUS_H
#define KITCHEN_HARDWARE_STATUS_H

#include <stdint.h>

#define HARDWARE_STATUS_MAGIC 0x5748534Bu

/* 日志对应：2026-09-21 多传感器统一数据结构；2026-09-25 本地端自测。
 * 固定 32 位字段顺序供 SWD 网关读取；修改布局时必须同步版本号和 Python FIELDS。 */
typedef struct {
    uint32_t magic;            /* 状态块识别码，避免误读其他 RAM 内容。 */
    uint32_t version;          /* 当前为 4；读取工具兼容旧版。 */
    uint32_t update_count;     /* 奇数正在写入；偶数为完整快照。 */
    uint32_t sequence;         /* 采样序号，用于确认主循环继续运行。 */
    uint32_t uptime_ms;        /* 上电运行时间，可辅助识别设备重启。 */
    uint32_t clock_hz;         /* 系统时钟，当前目标为 72 MHz。 */
    uint32_t smoke_raw;        /* PA0 烟雾 AO 的本轮原始 ADC 值。 */
    uint32_t temp_raw;         /* PA1 热敏 AO 的本轮原始 ADC 值。 */
    uint32_t gas_raw;          /* PA5 电位器原始值，用于模拟燃气相对指标。 */
    uint32_t flame_raw;        /* PA7 火焰 AO 原始值，信号增强时通常下降。 */
    uint32_t smoke_do;         /* PB5 转换后的低有效触发标志，1 表示触发。 */
    uint32_t flame_do;         /* PB1 转换后的低有效触发标志，1 表示触发。 */
    uint32_t alarm;            /* 任一测试危险位有效时为 1，具体类型见 hazard_flags。 */
    uint32_t servo_pulse_us;   /* TIM3 比较值；仅说明输出脉宽，不证明实际阀位。 */
    uint32_t gpio_a_output;    /* GPIOA 输出寄存器，不是执行器位置反馈。 */
    uint32_t gpio_b_output;    /* GPIOB 输出寄存器。 */
    uint32_t adc_error_count;  /* ADC 配置、启动和转换超时累计次数。 */
    uint32_t network_ready;    /* MB026 完成 TCP 透传连接才置 1。 */
    /* 日志对应：2026-09-22 数据滤波；2026-09-23 屏幕刷新。版本 2 在尾部增加诊断字段。 */
    uint32_t filtered_smoke_raw; /* 烟雾独立窗口的均值，不是标定浓度。 */
    uint32_t filtered_temp_raw;  /* 热敏均值，作为标称 NTC 换算输入。 */
    uint32_t filtered_gas_raw;   /* 电位器均值，作为燃气演示指标输入。 */
    uint32_t filtered_flame_raw; /* 火焰模拟通道均值，数字触发仍实时处理。 */
    int32_t temperature_centi_c; /* 标称公式估算，百分之一摄氏度；无效用 INT32_MIN。 */
    uint32_t temperature_valid;   /* 仅表示换算在模块量程内，不能代表已完成实物标定。 */
    uint32_t flame_detected;     /* 模拟极性与数字触发合并后的试验火焰判断。 */
    uint32_t filter_count;       /* 当前实际均值点数，启动后逐步达到 8。 */
    uint32_t display_update_count; /* 已向 OLED 刷新数据的次数，不是物理屏幕回执。 */
    uint32_t processing_test_failures; /* 同一 C 算法在 MCU 上执行自测，0 为通过。 */
    uint32_t smoke_enabled; /* 日志对应：2026-09-26。禁用通道的内部零值不能当作测量结果。 */
    /* 日志对应：2026-09-24。分别报告危险类型、阀门锁定与低压风扇演示配置。 */
    uint32_t hazard_flags;        /* bit0 燃气、bit1 火灾，可组合为复合危险。 */
    uint32_t valve_latched;       /* 当前运行期关阀指令已锁定，不是实际阀位传感器。 */
    uint32_t gas_fan_demo_enabled; /* 无可燃气体的低压台架风扇策略，火灾时强制关闭。 */
    /* 日志对应：2026-10-02。版本 4 增加可执行能力及信箱回执，旧字段位置保持不变。 */
    uint32_t control_capabilities; /* bit0～6 对应七种动作；仅 SWD 信箱可用。 */
    uint32_t command_sequence;     /* MCU 已处理的命令序号。 */
    uint32_t command_result;       /* 信箱结果码，不等于机械位置反馈。 */
    uint32_t silence_remaining_ms; /* 剩余消音时长，火灾会立即取消消音。 */
    uint32_t test_remaining_ms;    /* 剩余执行器测试时间，险情发生立即终止。 */
    uint32_t rules_revision;       /* 本地已应用的平台规则版本，0 使用编译默认值。 */
    uint32_t gas_threshold;        /* 当前实际用于本地保护的燃气相对阈值。 */
    uint32_t smoke_threshold;      /* 当前烟雾相对阈值。 */
    uint32_t temperature_threshold_centi; /* 当前温度阈值，百分之一摄氏度。 */
    /* 编写/修改日期（日志对应）：2026-10-15。版本 5 区分待机心跳、实际采样和限时演练。 */
    uint32_t monitoring_enabled; /* 0=待机，不执行 ADC 轮询；通信和受控启用仍工作。 */
    uint32_t sample_count; /* 实际 ADC 四通道采样轮数，待机保持不变。 */
    uint32_t test_scenario; /* 0 无注入，1 燃气、2 烟雾、3 高温、4 火焰、5 复合。 */
    uint32_t injection_remaining_ms; /* 演练十五秒后自动结束，历史报警仍保留。 */
    uint32_t effective_gas, effective_smoke; /* 带演练标记的保护输入，真实原始通道保持原值。 */
    int32_t effective_temperature_centi;
    uint32_t effective_flame;
    uint32_t wifi_state; /* 0 未配置、1 连接中、2 AT 失败、3 热点失败、4 TCP 失败、5 双向连接。 */
    uint32_t arming; /* 开始后的八点基线检查期间保持关阀。 */
    /* 日志对应：2026-10-15。版本6：缓存容量、待补传、溢出与稳定启动身份，供网页和SWD核查。 */
    uint32_t cache_pending,cache_capacity,cache_dropped,boot_identity;
} HardwareTestStatus;

extern volatile HardwareTestStatus g_hardware_status;

#endif

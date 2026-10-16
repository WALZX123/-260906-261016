# CubeMX 基础配置与答辩查看

对应日期：2026-10-15。配置文件：`KitchenSentinel_F103.ioc`。芯片为 STM32F103C8T6，LQFP48，实际 Flash 64 KiB、RAM 20 KiB。

用 STM32CubeMX 的 **File → Load Project** 打开 `.ioc`，在 **Pinout & Configuration** 看引脚和外设，在 **Clock Configuration** 看时钟树。项目实际运行入口仍是本目录内 `MDK-ARM/KitchenSentinel_F103.uvprojx`。本配置用于展示和核对已运行程序的基础参数，不能把它直接生成的空框架当作完整厨房监测程序。

本目录采用参考案例的 Core/Inc、Core/Src、Drivers、MDK-ARM 组织方式，包含实际运行源码。IOC和Keil工程已在同一根目录集成。重新生成会影响已修改的业务文件，应先备份并逐项核对差异；生成的初始化框架不会自动恢复本项目全部业务逻辑。软件 I²C、动态 ADC 逐通道选择、报警与启用状态机、无线协议、显示字模及 SWD 信箱由本项目代码实现。

## 引脚与运行代码对应

| 引脚 | CubeMX 标签／模式 | 实际用途与代码位置 |
| --- | --- | --- |
| PD0／PD1 | RCC OSC IN／OUT | 8 MHz 外部晶振，SYSTEM/sys/sys.c |
| PA0 | ADC1 IN0 | 烟雾 AO；AO→10kΩ→PA0，PA0→20kΩ→GND |
| PA1 | ADC1 IN1 | NTC 热敏 AO，标称参数估算温度 |
| PA5 | ADC1 IN5 | 电位器模拟燃气相对指标，不是标定浓度 |
| PA7 | ADC1 IN7 | 火焰 AO，信号增强时模拟值下降 |
| PB5／PB1 | 上拉输入，低有效 | 烟雾 DO 诊断／火焰 DO 实时保护 |
| PA2 | 高速推挽输出、上拉 | OLED 软件 I²C SCL，与原厂实际实现一致 |
| PA3 | 高速开漏输出、上拉 | OLED 软件 I²C SDA |
| PA6 | TIM3 CH1 PWM | 舵机模拟阀门，500 μs 关阀、1500 μs 开阀 |
| PB0 | 低速推挽，初始低 | 蜂鸣器，高有效 |
| PA8／PB13 | 低速推挽，初始低 | 风机正向／反向；反向保持低，火灾停风机 |
| PB12 | 低速推挽，初始低 | 低压继电器保护输出 |
| PA9／PA10 | USART1 TX／RX | 115200、8N1 调试遥测串口 |
| PB10／PB11 | USART3 TX／RX | MB026：PB10→模块 RXD，PB11←模块 TXD |
| PA4 | 推挽输出 | MB026 低有效复位；连接状态机产生复位脉冲 |
| PA13／PA14 | Serial Wire | SWDIO／SWCLK，保留下载和调试 |

GPIO 标签里的 WIFI_RXD、WIFI_TXD 指模块端的接线名称，USART3_TX、USART3_RX 指 STM32 端功能；答辩时应说明收发交叉连接。

## 关键时序与公式

| 项目 | 实际配置与解释 |
| --- | --- |
| 系统时钟 | HSE 8 MHz，PLL ×9，SYSCLK／AHB 72 MHz |
| APB1 | 36 MHz；分频不为 1 时，TIM2／TIM3 时钟乘 2，得到 72 MHz |
| APB2／ADC | APB2 72 MHz，ADC 分频 6，ADC 时钟 12 MHz |
| 单次 ADC | 239.5 周期采样＋12.5 周期转换＝252 周期，理论约 21 μs；四次约 84 μs，不含 HAL 与任务开销 |
| 采集方式 | 单次软件触发、右对齐、12 位；运行时逐次重配通道 0／1／5／7。未使用 DMA、连续扫描或定时器触发采集 |
| 均值滤波 | 每路独立 8 点窗口；启动不足八点时按实际点数平均，不用零值补齐。窗口响应与实际采样周期有关 |
| 舵机计数 | TIM3：72 MHz ÷(71＋1)＝1 MHz，每计数 1 μs |
| 舵机周期 | ARR＝19999，周期 (19999＋1) μs＝20 ms，频率 50 Hz |
| 舵机占空比 | 关阀 500／20000＝2.5%；开阀 1500／20000＝7.5%。舵机依据脉宽位置控制，不能只说占空比 |
| UART 帧时间 | 115200、8N1，每字节 1 起始＋8 数据＋1 停止，共 10 位，约 86.8 μs／字节 |
| 串口收帧 | TIM2：PSC＝7199、ARR＝99；100 μs×100＝10 ms 空闲判帧。UART 中断写入512字节连续流环形缓冲；主循环按换行解析TCP，原10ms空闲AT帧仅供连接阶段 |
| SysTick | 1 ms HAL 时间基准，优先级 15；毫秒计数不是直接当成日期时间 |
| 中断优先级 | USART3、TIM2 为 0，USART1 为 3；NVIC 分组 4 下子优先级不参与排序 |
| 主循环 | 目标 100 ms；ADC、判定、保护、显示在同轮先执行，阻塞通信耗时计入周期，不能把目标周期直接当实测频率 |
| 网络上报 | 500 ms 节流，Wi-Fi 与调试串口共享同一帧；局部显示和保护不必等待每次网络发布 |
| OLED | 软件 I²C，原厂位延时 2 μs；时钟还包括 GPIO 与 ACK 开销，不能据此宣称测得 250 kHz。连续写变化页以减少总线占用 |
| 限时动作 | 执行器分项测试 3 秒，消音 15 秒，险情注入 15 秒；火灾取消消音，真实故障优先取消演练 |
| 回绕处理 | HAL 毫秒为 32 位，无符号差求间隔、有符号差判断短截止时间；无线心跳同轮更新后刷新 now，避免旧时间减新时间误判断线 |

## 开始运行与保护顺序

上电先关阀待机 → 网页可写账号启用 → 建立八点基线 → 无险情开阀 → 持续采样与本地判断 → 对应保护输出 → 数据和回执上传。燃气模型报警开启低压风机；烟雾、高温、火焰或复合火灾停止普通风机。险情恢复只恢复信号状态，关阀保持；由操作人员另行执行“恢复运行并开阀”。报警记录的人工确认不会自动开阀。

无线配置保存在最后 1 KiB Flash；应用链接区为 `0x08000000` 至 `0x08009FFF`（40KiB）；`0x0800A000`至`0x0800FBFF`为23KiB离线队列，配置页从 `0x0800FC00` 起。密码和认证密钥不在 `.ioc`、工程 ZIP 或 HEX 中。配置页保存的是本机配置，不保存采样启用状态；重新上电仍先待机。

CubeMX 官方说明：[UM1718](https://www.st.com/resource/en/user_manual/dm00104712-stm32cubemx-for-stm32-configuration-and-initialization-c-code-generation-stmicroelectronics.pdf)。配置导入和导出也可通过官方命令行完成：[CubeMX CLI](https://dev.st.com/stm32cube-docs/stm32cubemx/6.18.0/en/docs/markup/CubeMX_CLI.html)。本项目的实际加载和寄存器核验结果另外保存在 `.runtime/hardware-test`，以验收记录为准。

## 本机实际导入结果

2026-10-15 使用已安装 STM32CubeIDE1.17 中的 CubeMX6.13 引擎，完成 config load、csv pinout 与 config save，均返回 OK；导出48个物理封装引脚，IOC无无效项目参数。Pinout_CubeMX_2026-10-15.csv 为实际导出文件。通过隔离副本验证，保留主配置的中文说明，避免工具规范化保存时删除注释。

安装位置为 E:/STM32CubeIDE_1.17.0/STM32CubeIDE，相关插件 com.st.stm32cube.common.mx_6.13.0.202411220809。本机存在较新第三方扩展包缓存不兼容及内嵌浏览器缓存解压诊断，但不影响这次配置导入、保存和引脚导出。此处验收的是实际配置引擎，未逐项点击图形界面。若在IDE中使用，选择STM32CubeMX配置编辑器查看IOC。

运行中寄存器只读核验：TIM2 PSC7199／ARR99，TIM3 PSC71／ARR19999／CCR1=1500，SysTick LOAD71999，USART1 BRR625，USART3 BRR312，ADC四路239.5周期，与配置一致。20:02五秒窗口内显示与采样实测约7.33Hz，目标100ms不是保证10Hz。

## 当前显示与下载入口（2026-10-16）

固件6.0采用14×14中文与6×12数字，四行核心信息；用户确认可读。OLED首帧位于ADC/Flash/联网前。Keil目标Download按F7实际下载成功；Template仅编译。状态ABI6增加575条队列容量、待传数、缺口及启动身份。配置校验日志为.runtime/hardware-test/cubemx/validate_integrated.log，48脚CSV随当前IOC放置；本机浏览器缓存与扩展包诊断不是IOC参数错误。

# STM32F103 硬件测试固件

这个目录是厨房安全项目的 STM32F103C8T6 实物联调工程，基于参考工程复制后加入本项目的测试入口。Keil 工程位于 `Projects/MDK-ARM/atk_f103.uvprojx`，源码入口为 `Users/demo.c`。

已实现的测试项：

- ADC1：PA0 烟雾 AO、PA1 热敏电阻 AO、PA5 气体测试电位器、PA7 火焰 AO；
- 数字输入：PB5 烟雾 DO、PB1 火焰 DO；
- 输出：PB0 蜂鸣器、PB12 低压继电器、PA8/PB13 风机正反控制；
- TIM3_CH1：PA6 舵机，上电未报警时输出 90° 指令，危险触发后保持 0° 关闭指令，信号恢复不自动重新开阀；实际动作需现场确认；
- OLED：PA2/PA3，实时显示相对指标、温度估算、火焰、输出状态及未标定标记；
- USART1：PA9/PA10，115200 8N1，每轮采样打印一帧 JSON 及网络状态；
- SWD：通过 `g_hardware_status` 读取一致的实时 ADC、数字输入、PWM、GPIO 输出和故障状态，无需先接通串口；
- ATK-MB026：PB10/PB11、PA4 复位，配置 Wi-Fi 后通过 TCP 9000 上报同一帧 JSON。默认不配置 Wi-Fi，固件照常进行本地采样。

气体和烟雾字段是 0 到 100 的相对量，未经标定不能解释为 ppm 或 %LEL。版本 2 对四路 ADC 使用独立的 8 点滑动均值，并按原厂标称 NTC 参数估算温度；不是实物校准结果，`valid=false` 保留。端点或超出模块量程的温度输出 `null`。烟雾传感器 AO 若为 5 V，必须先经过接线说明中的分压；继电器只连接低压测试负载。火焰 AO 随信号增强而下降，DO 为低有效，模拟阈值仍需标定。

## 当前版本 4（2026-10-15）

33,560 字节已下载读回一致；本轮自检及蜂鸣器、风扇、继电器和舵机关阀命令都有固件回执，用户确认动作正常。阈值按平台版本同步，断线继续使用最后有效值。普通燃气模型响应保留关阀、排风和鸣响；火灾停止普通风扇并转人工。

全部实际编译源文件及头文件在本工程内，包括本地 C 标准头文件副本。已开启 Browse Information 并完整重建；DeviceSupport 中附原厂器件包。详见项目 docs/Keil工程与答辩代码导览_2026-10-15.md。原厂库版权保留，实际引用文件已补充中文职责与接口说明。

## 历史验证记录

以下保留各版本当时的测试事实；旧版控制限制及舵机故障记录已由上述版本 4 和本轮现场反馈更新。

## 已验证

- Keil MDK 5.35 / ARM Compiler 5.06u7：`0 Error(s), 0 Warning(s)`；
- 已生成并实际烧录 `Output/atk_f103.hex`；2026-10-15 版本 3 的 32,804 字节全部读回一致；
- 目标芯片读回 STM32F103C8、DAP ID `0x1BA01477`、Flash 64 KB；
- 实机 72 MHz 时钟和采样循环持续运行，ADC 错误计数、CFSR、HFSR 均为 0；用户已确认接线修正后蜂鸣器正常；
- 工程的 `.uvoptx` 已绑定 `ATK-20240820`、DAP ID `0x1BA01477`，Keil 界面调试频率为 500 kHz。实际下载使用下述已验证的 pyOCD 入口。

## 下载前检查

1. 保持 ATK-CMSIS-DAP 的 SWDIO、SWCLK、GND、3.3 V 和 NRST 接线，目标板与探针共地。
2. 不要把 5 V 烟雾 AO 直接接 PA0。
3. 若只做本地串口测试，无需 Wi-Fi。在 `Users/network_config.h` 填入实际 2.4 GHz Wi-Fi 和电脑局域网 IPv4 后重编译，才会启用 MB026 TCP 上报；不要沿用参考工程中的演示 SSID、密码或 IP。
4. 无线测试前先从项目根目录运行 `python -m scripts.register_hardware`，再运行 `python -m gateway.server --listen-host <电脑局域网IPv4>`。网关从项目 `.env` 读取独立硬件令牌，转发到 `stm32-001`。串口日志需要调试器 CDC 与 PA9/PA10 实际相连；COM3 枚举本身不能证明这两根 UART 信号线已接通。

版本 4 已接入 SWD 命令信箱：关阀、限时消音、自检及短时执行器测试由固件执行并回执，阈值以版本化信箱同步。该链路依赖当前电脑与调试器；Wi-Fi 控制仍未验收。

## 已解决的烧录问题与重复测试入口

ATK-CMSIS-DAP 固件 2.1.2 在多个命令同时排队时出现应答错位，OpenOCD 实测报 `Expected 0x5 received 0x6`，pyOCD 默认配置会在大块读取或擦除时停住。使用 `cmsis_dap.limit_packets=true`、`cmsis_dap.deferred_transfers=false` 和 500 kHz 后，完整读取、擦除、写入和逐字节校验均通过。该配置已经固化到 `tools/hardware_test.py`。烧录前会复位并暂停内核，避免在中断上下文运行 Flash 算法。

该探针的默认退出流程还会让 MCU 重新启动。工具已改为先退出 CPU 调试、再关闭 HID 通道，避开会触发重启的探针断开命令。退出并重新运行监视工具的实测结果：采样序号 72→75、运行时间 75,020→78,122 ms，未重启。

从本固件目录运行一键编译、备份、下载、读回校验和实机采样检查：

```powershell
& '.\tools\flash.ps1'
```

从 `kitchen-sentinel` 项目根目录只读观察真实采样：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\firmware\stm32f103_hardware_test\tools\hardware_test.py' status --samples 15
```

工具需要项目 `.venv` 中的 pyOCD 0.45.1（含 IntelHex）和 `.runtime/hardware-test/Keil.STM32F1xx_DFP.2.3.0.pack`。固件源码和工具都保存在本目录；原程序备份、读回镜像、烧录结果 JSON、实机样本 JSONL 保存在项目 `.runtime/hardware-test`，不进入 Git。下载失败时不会自动启动部分写入的程序。Keil 的原生 Flash 下载器仍存在兼容问题，后续下载应使用已验证的入口。

当前实时数据来源是 `hardware`、通道是 `swd`。COM3 已能打开，但最近监听未收到 USART1 文本；Wi-Fi 未配置，`network_ready=0`。这两条通信链路尚待单独验证。ADC 原始值已经能够采集，输入极性、量程和报警阈值仍需逐个模块标定，不能把当前测试报警解释为实际火灾。

## 实物数据接入看板

项目根目录执行 `python start.py --hardware` 会启动后端和 `gateway.swd`。真实 RAM 快照经严格范围校验后上报，数据库保存历史指标、最新原始值与滤波值，网页标记“STM32 实物采样 · 调试器连接”。温度按标称公式估算，数据质量标记待标定；控制状态来自寄存器，不表示实际阀位反馈。

2026-10-14 已验证真实数据写入 MySQL、历史查询、WebSocket 推送和网页显示；硬件远程命令返回 409，防止未实现的执行回执被误显示为成功。原始证据位于项目 `.runtime/hardware-test/swd_ingest.jsonl`、`pipeline_check.json`。

源码注释以新版《实习日志 .xlsx》对应日期标记：采集 2026-09-21，显示 2026-09-23，联动 2026-09-24，自测 2026-09-25，异常处理 2026-09-26，上报 2026-09-30。原厂版权和作者信息保留。

2026-10-15 版本 2：新增 `Users/sensor_processing.c/.h`，8 点均值、NTC 估算和火焰极性处理均在 MCU 上运行，并执行已知向量自测。状态块新增滤波值、带符号温度、滤波点数、OLED 刷新计数和自测失败位。`scripts/analyze_hardware_samples.py` 对真实连续采样窗口逐项复算均值；结果保存在 `.runtime/hardware-test/sensor_processing_check.json`。屏幕显示与操作变化已收到用户肯定反馈；温度精度、烟雾量程和执行器物理动作仍需分别核验。

接线处理记录：原先烟雾 AO 直连 PA0，连续 163 帧均为 4095，因此暂停采集。用户现已确认接入 `AO → 10kΩ → PA0`、`PA0 → 20kΩ → GND`。13:23 复测烟雾原始值 1126–1339，13:25 恢复持续采集后首轮范围 634–726，未再满量程。当时运行版本 2。13:42 已烧录版本 3，烟雾通道启用，状态块增加危险类型、阀门锁定和风扇演示开关。

版本 3 保留自动关模拟阀、蜂鸣器与低压保护输出，火灾禁止普通风扇，燃气风扇演示默认关闭；阀门锁定只保存在当前 MCU 运行期间。新增 `Users/response_policy.c/.h` 及板上向量自测，失败位为 0。PC 报警确认不会改变输出，也不会复位阀门锁定。

2026-10-15 舵机现场反馈：蜂鸣器正常，舵机未转动。13:55 只读检查确认 PA6 为复用推挽、TIM3 未重映射、计数器及通道已启用，周期 20 ms、关闭脉宽 500 μs；PA6 回读有高低电平。这些不能证明舵机实际转动，供电、线序和机械连接仍需核查。本次报警已按现场反馈转人工检查。

停止统一运行入口并确认采集已退出后，可在项目根目录执行只读诊断：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\firmware\stm32f103_hardware_test\tools\hardware_test.py' servo-status
```

完整证据见项目 `docs/实机测试记录_2026-10-15.md` 和 `docs/自动响应与人工确认处理规则.md`。

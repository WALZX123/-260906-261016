# STM32F103C8T6 硬件接线与软件联调说明

本文按照项目当前的生产实习原型范围编写，使用 M48Z-M3 STM32F103C8T6 小系统板、BEE BLOCK 烟雾、热敏、火焰、OLED、蜂鸣器、继电器、风扇、舵机和 ATK-MB026 WIFI & BLE 模块。阀门使用舵机模拟，继电器只控制低压模拟负载。

## 先确认供电

1. STM32 小系统板通过 Type-C 供电。
2. 烟雾模块 ATK-MB005 必须接 5V；它的 AO 最高可能接近 4V，不能直接接 STM32 ADC。
3. 热敏、火焰、电位器和 OLED 使用 3.3V 供电，避免模拟输出超过 ADC 输入范围。
4. 蜂鸣器、继电器、风扇、舵机和 ATK-MB026 使用外部 5V 供电。外部 5V 电源建议不低于 2A。
5. 所有模块的 GND 必须和 STM32 的 GND 相连。外部电源只共地，不要在 Type-C 供电时把两个独立的 5V 正极直接并联。
6. 先断电接线，接好后用万用表确认 VCC 与 GND 之间没有短路，再接通电源。

## 推荐引脚分配

| 模块 | 模块引脚 | STM32 引脚 | 说明 |
|---|---|---|---|
| ATK-MB005 烟雾 | VCC | 外部 5V | 模块要求 5V |
| ATK-MB005 烟雾 | GND | GND | 共地 |
| ATK-MB005 烟雾 | AO | 分压后接 PA0 / ADC1_IN0 | AO 先经过 10kΩ 串联、20kΩ 下拉分压 |
| ATK-MB005 烟雾 | DO | 分压后接 PB5 | 数字输出也按 5V 输出处理，不能直接假设为 3.3V |
| ATK-MB002 热敏 | VCC | 3.3V | 模块支持 3.3V~5V |
| ATK-MB002 热敏 | GND | GND | 共地 |
| ATK-MB002 热敏 | AO | PA1 / ADC1_IN1 | 用 AO 计算温度 |
| ATK-MB002 热敏 | DO | 暂不接 | 温度阈值由软件规则统一判断 |
| ATK-MB007 火焰 | VCC | 3.3V | 模块支持 3.3V~5V |
| ATK-MB007 火焰 | GND | GND | 共地 |
| ATK-MB007 火焰 | AO | PA7 / ADC1_IN7 | 读取火焰强度相对值 |
| ATK-MB007 火焰 | DO | PB1 | 低电平表示超过模块比较器阈值 |
| ATK-MB012 电位器 | VCC | 3.3V | 用作燃气值模拟输入 |
| ATK-MB012 电位器 | GND | GND | 共地 |
| ATK-MB012 电位器 | AO | PA5 / ADC1_IN5 | 旋钮值映射为 0~100 的燃气相对指标 |
| ATK-MB022 OLED | VCC | 3.3V | I2C 模块 |
| ATK-MB022 OLED | GND | GND | 共地 |
| ATK-MB022 OLED | SDA | PA3 | 按模块示例使用软件 I2C |
| ATK-MB022 OLED | SCL | PA2 | 按模块示例使用软件 I2C |
| ATK-MB003 蜂鸣器 | VCC | 外部 5V | 有源蜂鸣器 |
| ATK-MB003 蜂鸣器 | GND | GND | 共地 |
| ATK-MB003 蜂鸣器 | BZZ | PB0 | 高电平打开，低电平关闭 |
| ATK-MB010 继电器 | VCC | 外部 5V | 继电器线圈供电 |
| ATK-MB010 继电器 | GND | GND | 共地 |
| ATK-MB010 继电器 | IN | PB12 | 高电平吸合，低电平释放 |
| ATK-MB010 继电器 | COM/NO | 低压模拟负载 | 只接 5V 灯或小负载，禁止接市电 |
| ATK-MB023 风扇 | VCC | 外部 5V | 模块自带电机驱动 |
| ATK-MB023 风扇 | GND | GND | 共地 |
| ATK-MB023 风扇 | FI | PA8 / TIM1_CH1 | 正转 PWM 或高电平 |
| ATK-MB023 风扇 | BI | PB13 / TIM1_CH1N | 停止时拉低；不要和 FI 同时输出高电平 |
| 舵机模块 | 红线 VCC | 外部 5V | 舵机不要从 STM32 3.3V 取电 |
| 舵机模块 | 棕线 GND | GND | 与 STM32 共地 |
| 舵机模块 | 橙线 DI | PA6 / TIM3_CH1 | 50Hz PWM，作为模拟阀门角度 |
| ATK-MB026 WIFI | VCC | 外部 5V | 模块板带 5V 接口 |
| ATK-MB026 WIFI | GND | GND | 共地 |
| ATK-MB026 WIFI | TXD | PB11 / USART3_RX | 模块 TX 接单片机 RX |
| ATK-MB026 WIFI | RXD | PB10 / USART3_TX | 模块 RX 接单片机 TX |
| ATK-MB026 WIFI | RST | PA4 | 按模块 STM32F103 示例保留默认复位脚，低电平复位，高电平运行 |
| ATK-MB026 WIFI | IO_9 | 暂不接 | 当前 TCP 透传方案不需要 |

## 烟雾 AO 和 DO 的分压

烟雾模块供电为 5V，资料说明 AO 最高可能达到 4V。每个需要接入 STM32 的 5V 输出都使用一组分压：烟雾 AO 接 10kΩ 电阻后到 PA0，PA0 再通过 20kΩ 电阻接 GND；烟雾 DO 也使用同样的 10kΩ/20kΩ 分压后接 PB5。分压后的 4V 约为 2.67V，处于 STM32 ADC 安全范围内。

## 模块联动逻辑

- 电位器值映射为 `gas`，只写入 0~100 的燃气相对指标，不写成真实 ppm。
- 当前四路 ADC 使用独立的 8 点滑动均值；烟雾均值映射为 `smoke` 0~100，原始值另存。
- 热敏 AO 按原厂 10k NTC、B=3950 的标称参数估算温度，尚未做实物温度校准。
- 火焰 DO 低有效；AO 随火焰增强而下降，当前模拟判断采用低于试验阈值的方向。
- `gas` 超过规则阈值时，舵机转到关闭角度，风扇启动，蜂鸣器打开。
- 火焰或烟雾超过阈值时，蜂鸣器、LED 和继电器进入火灾演示状态。
- 继电器只连接低压灯或小风扇作为非消防负载模拟。
- 阀门状态在当前原型中是舵机角度状态，不代表真实燃气阀门的物理反馈。

## WIFI 通信方式

ATK-MB026 的资料给出的 STM32F103 连接关系是：VCC=5V、GND=GND、TXD=PB11、RXD=PB10，默认串口为 115200 8N1。模块自身负责连接 Wi-Fi 和 TCP 服务器，STM32 通过 UART 发送 JSON 行数据。

当前电脑端后端提供 HTTP 设备接口 `/api/v1/ingest/devices/{device_id}/telemetry`，本机 TCP 遥测网关已经位于 `gateway` 目录：ATK-MB026 连接网关端口，网关接收 STM32 的 JSON，补齐设备身份和时间后转发到 FastAPI。远程控制与硬件回执尚未接入；当前网关不轮询或下发控制命令。

## 当前软件检查结果

已经具备：FastAPI 设备遥测接口、设备 Bearer 令牌认证、遥测去重、报警规则、报警历史、设备离线判断、控制命令、命令回执、审计日志、WebSocket 快照和独立模拟器。

2026-10-14 已完成 STM32F103 固件工程和 GPIO/ADC/PWM/UART 驱动、TCP 遥测网关，以及实际烧录和 SWD 实时采样验证。烧录使用 `firmware/stm32f103_hardware_test/tools/flash.ps1`，真实 ADC 样本可用同目录 `hardware_test.py status` 读取。蜂鸣器接线修正后用户已确认正常发声。

2026-10-14 已完成 `stm32-001` 独立硬件节点注册，并通过 SWD 网关把实机数据写入 MySQL、历史查询和 WebSocket 看板。网页默认显示硬件节点及原始通道；`kitchen-001` 仍为独立模拟节点。硬件联调入口为项目根目录的 `python start.py --hardware`。

后续待验证：USART1 与 COM3 实际收发、MB026 Wi-Fi/TCP 上报、输入量程与报警阈值标定、继电器/风扇/舵机物理动作，以及远程控制回执。硬件当前只支持采样上报和本地测试联动，远程控制按钮禁用，接口返回 409。

## 资料位置

模块原始资料位于项目上级目录的 `【正点原子】BEE BLOCK模块资料合集\套件硬件资料（合集）`，本说明使用了 ATK-MB002、ATK-MB003、ATK-MB005、ATK-MB007、ATK-MB010、ATK-MB022、ATK-MB023、ATK-MB026 和舵机模块的用户手册及 STM32F103 示例工程。

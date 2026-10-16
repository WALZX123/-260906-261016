"""文件职责：CubeMX 基础配置与实际固件参数一致性回归。
主要功能：交叉核对晶振、分频、PWM、软件 I²C 和全部已连接引脚，防止答辩配置与代码分离。
技术栈：pytest、属性文件解析、C 参数扫描；模块联动：CubeMX 配置和真实 Keil 工程。
编写/修改日期（日志对应）：2026-10-15。此检查不替代 CubeMX 软件实际加载。
"""
from pathlib import Path
import re

FW = Path(__file__).resolve().parents[1] / 'firmware/stm32f103_hardware_test/CubeMX'


def properties():
    """读取非注释属性并拒绝重复键，避免 CubeMX 悄悄使用被覆盖的旧参数。"""
    values = {}
    for line in (FW / 'KitchenSentinel_F103.ioc').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        assert key not in values
        values[key] = value
    return values


def test_cubemx_matches_clock_pwm_and_wireless_timer():
    """基础时钟与两个定时器按源代码交叉计算，既检查频率也检查实际外设选择。"""
    cfg = properties()
    main = (FW / 'Core/Src/main.c').read_text(encoding='utf-8-sig')
    demo = (FW / 'Core/Src/demo.c').read_text(encoding='utf-8-sig')
    assert cfg['Mcu.CPN'] == 'STM32F103C8T6'
    assert 'sys_stm32_clock_init(RCC_PLL_MUL9)' in main
    assert int(cfg['RCC.HSE_VALUE']) * 9 == int(cfg['RCC.SYSCLKFreq_VALUE']) == 72000000
    psc = int(re.search(r'htim3.Init.Prescaler = (\d+)', demo)[1])
    arr = int(re.search(r'htim3.Init.Period = (\d+)', demo)[1])
    assert psc == int(cfg['TIM3.Prescaler']) and arr == int(cfg['TIM3.Period'])
    assert 72000000 / (psc + 1) / (arr + 1) == 50
    assert cfg['RCC.ADCPresc'] == 'RCC_ADCPCLK2_DIV6'
    assert int(cfg['TIM2.Prescaler']) == 7199 and int(cfg['TIM2.Period']) == 99
    assert cfg['USART3.BaudRate'] == cfg['USART1.BaudRate'] == '115200'


def test_cubemx_preserves_sensor_and_actuator_pin_roles():
    """所有项目接线有标签，软件 I²C 不误配 I2C1，ADC 不占蜂鸣器与舵机引脚。"""
    cfg = properties()
    pins = {value for key, value in cfg.items() if re.fullmatch(r'Mcu.Pin\d+', key)}
    assert len(pins) == int(cfg['Mcu.PinsNb'])
    expected = {'PA0-WKUP': 'ADCx_IN0', 'PA1': 'ADCx_IN1', 'PA5': 'ADCx_IN5', 'PA7': 'ADCx_IN7',
                'PA6': 'S_TIM3_CH1', 'PB0': 'GPIO_Output', 'PB1': 'GPIO_Input', 'PB5': 'GPIO_Input',
                'PB10': 'USART3_TX', 'PB11': 'USART3_RX', 'PB12': 'GPIO_Output', 'PB13': 'GPIO_Output',
                'PA8': 'GPIO_Output', 'PA2': 'GPIO_Output', 'PA3': 'GPIO_Output', 'PA4': 'GPIO_Output'}
    for pin, signal in expected.items():
        assert pin in pins and cfg[pin + '.Signal'] == signal
        assert cfg[pin + '.GPIO_Label']
    assert cfg['PA2.GPIO_ModeDefaultOutputPP'] == 'GPIO_MODE_OUTPUT_PP'
    assert cfg['PA3.GPIO_ModeDefaultOutputPP'] == 'GPIO_MODE_OUTPUT_OD'
    assert not any(value == 'I2C1' for key, value in cfg.items() if key.startswith('Mcu.IP'))

"""文件职责：实物采样接口与数据边界测试。
主要功能：覆盖快照去重、重启身份、原始通道、滤波温度、隔离通道和硬件控制限制。
技术栈：pytest、Pydantic、SQLAlchemy SQLite、FrameBuilder。
模块联动：调用网关转换与 monitoring 入库，在隔离数据库核验来源和命令拒绝，不修改实物采样记录。
编写/修改日期（日志对应）：2026-09-25。
"""
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from backend.core.db import Base
from backend.domain.rules import DEFAULT_RULES
from backend.models import Device, RuleConfig, Telemetry, Command
from backend.schemas import SampleInput
from backend.services.monitoring import ingest, snapshot, create_command
from gateway.swd import FrameBuilder


def state(sequence=10, uptime=10000):
    """构造明确的测试快照，便于检查映射，不伪称来自实际传感器。
    编写/修改日期（日志对应）：2026-09-25。
    """
    return dict(sequence=sequence, uptime_ms=uptime, smoke_raw=1200, temp_raw=2200,
                gas_raw=4095, flame_raw=3500, smoke_do=0, flame_do=0, alarm=1,
                servo_pulse_us=500, gpio_a_output=1 << 8, gpio_b_output=(1 << 12) | 1)


def test_swd_frames_keep_raw_values_and_rotate_identity_on_mcu_reset():
    """重复读同一快照不重发；真实设备重启后可重新从序号零开始。
    编写/修改日期（日志对应）：2026-09-25。
    """
    builder = FrameBuilder()
    first = builder.build(state())
    assert builder.build(state()) is None
    second = builder.build(state(11, 11000))
    assert first['boot_id'] == second['boot_id']
    restarted = builder.build(state(0, 1000))
    assert restarted['boot_id'] != first['boot_id']
    assert first['gas'] == 100 and first['raw']['gas_ao'] == 4095
    assert first['transport'] == 'swd' and not first['valid']
    assert first['actuators']['buzzer'] == 'on'
    assert first.get('temperature') is None


def test_api_validates_adc_and_digital_ranges():
    """拒绝超出 12 位 ADC 量程和数字输入范围的错误数据。
    编写/修改日期（日志对应）：2026-09-25。
    """
    packet = FrameBuilder().build(state())
    packet['raw']['gas_ao'] = 5000
    with pytest.raises(ValidationError):
        SampleInput.model_validate(packet)
    packet['raw']['gas_ao'] = 4095
    packet['raw']['flame_do'] = 2
    with pytest.raises(ValidationError):
        SampleInput.model_validate(packet)


def test_version_two_uses_firmware_temperature_filter_and_flame_polarity():
    """日志对应：2026-09-22。保留原始量，展示板上计算结果，不把高 ADC 当作火焰增强。
    """
    board = state()
    board.update(version=2, temperature_centi_c=-350, temperature_valid=1, flame_detected=0,
                 filtered_smoke_raw=1000, filtered_temp_raw=3000, filtered_gas_raw=2048,
                 filtered_flame_raw=4095)
    packet = FrameBuilder().build(board)
    assert packet['temperature'] == -3.5 and not packet['valid']
    assert packet['raw']['gas_ao'] == 4095 and packet['filtered']['gas_ao'] == 2048
    assert packet['gas'] == 50 and not packet['flame']
    assert packet['firmware'] == 'stm32f103-hwtest/2.0'


def test_invalid_temperature_remains_missing_instead_of_becoming_zero():
    """日志对应：2026-09-26。换算失败不能显示伪造的零摄氏度。
    """
    board = state()
    board.update(temperature_valid=0, temperature_centi_c=-2147483648)
    assert FrameBuilder().build(board).get('temperature') is None


def test_hardware_snapshot_history_and_command_boundary():
    """检查入库去重、来源标记、令牌隐藏，以及不生成未实现的硬件控制命令。
    编写/修改日期（日志对应）：2026-09-25。
    """
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Device(id='kitchen-001', name='sim', location='test', token_hash='test', source='simulated'),
            Device(id='stm32-001', name='STM32', location='test', token_hash='test', source='hardware'),
            RuleConfig(id=1, revision=1, values=DEFAULT_RULES.copy()),
        ])
        db.commit()
        packet = FrameBuilder().build(state())
        packet['firmware'] = 'stm32f103-hwtest/2.0'
        packet['sampled_at'] = datetime.now(timezone.utc).isoformat()
        sample = SampleInput.model_validate(packet)
        result = ingest(db, 'stm32-001', sample)
        duplicate = ingest(db, 'stm32-001', sample)
        assert result['accepted'] and not result['duplicate']
        assert duplicate['duplicate']
        assert db.scalar(select(func.count()).select_from(Telemetry)) == 1
        assert db.scalar(select(Telemetry)).sample_context['transport'] == 'swd'
        view = snapshot(db)
        hardware = view['devices'][0]
        assert hardware['id'] == 'stm32-001' and hardware['source'] == 'hardware'
        assert hardware['latest']['raw']['gas_ao'] == 4095
        assert hardware['latest']['transport'] == 'swd'
        assert hardware['firmware'] == 'stm32f103-hwtest/2.0'
        assert 'token_hash' not in hardware
        with pytest.raises(HTTPException) as error:
            create_command(db, 'stm32-001', 'silence', 'test', 'test-key-123')
        assert error.value.status_code == 409
        assert db.scalar(select(func.count()).select_from(Command)) == 0


def test_isolated_smoke_sensor_is_missing_instead_of_a_zero_measurement():
    """日志对应：2026-09-26。隔离通道不能写成零浓度或有效零 ADC。
    """
    board = state()
    board.update(smoke_enabled=0, smoke_raw=0, filtered_smoke_raw=0)
    packet = FrameBuilder().build(board)
    assert packet.get('smoke') is None
    assert packet['raw'].get('smoke_ao') is None and packet['raw'].get('smoke_do') is None
    assert packet['filtered'].get('smoke_ao') is None
    assert packet['disabled_sensors'] == ['smoke'] and not packet['valid']

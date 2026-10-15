"""文件职责：自动响应、异常留档和人工确认回归。
主要功能：核验能力内自动保护、火灾或失败升级、恢复留档、重复事件及确认不会撤销保护。
技术栈：pytest、SQLAlchemy SQLite、纯领域规则、接口函数。
模块联动：对照 response、rules、monitoring 与 platform；测试库与真实报警分开，控制输出不能冒充实际阀位。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-12。
"""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from backend.core.db import Base
from backend.domain.rules import DEFAULT_RULES, evaluate
from backend.domain.response import evaluate_response
from backend.models import Alarm, Device, Command, RuleConfig, utcnow
from backend.api.platform import acknowledge, resolve_alarm, escalate_alarm
from backend.schemas import NoteInput, RuleInput
from backend.services.monitoring import sync_alarm


def response(kind='gas', active=True, elapsed=1, gas=55, previous=None, failed=False):
    """构造自动保护反馈并调用纯处置函数，让用例分别改变危险类型、指标、时长和失败状态。
    编写/修改日期（日志对应）：2026-10-12。
    """
    return evaluate_response(kind, active, elapsed, {'gas': gas},
        {'valve': 'closed', 'fan': 'off', 'buzzer': 'on', 'power': 'on'}, DEFAULT_RULES, previous, failed=failed)


def test_gas_remains_automatic_within_capability():
    """验证能力内燃气异常保持自动保护和效果观察，不强制升级人工处置。
    编写/修改日期（日志对应）：2026-10-12。
    """
    value = response()
    assert value['automatic_status'] == 'monitoring'
    assert not value['manual_required']
    assert all(action['matched'] for action in value['actions'])


def test_automatic_recovery_does_not_require_manual_danger_handling():
    """验证普通测试信号恢复后不增加人工处置要求，报警确认仍由独立字段决定。
    编写/修改日期（日志对应）：2026-10-12。
    """
    value = response(active=False, elapsed=10, gas=8, previous=response())
    assert value['automatic_status'] == 'signal_recovered'
    assert not value['manual_required']


def test_simulated_automatic_closed_loop_is_distinguished_from_pin_feedback():
    """验证只有有效模拟器闭环可标记模拟自动完成，不把实物控制引脚反馈当作现场成功。
    编写/修改日期（日志对应）：2026-10-12。
    """
    value = evaluate_response('gas', False, 10, {'gas': 8, 'valid': True},
                              {'valve': 'closed'}, DEFAULT_RULES, source='simulated')
    assert value['automatic_status'] == 'auto_resolved' and not value['manual_required']


@pytest.mark.parametrize('kwargs,reason', [
    ({'gas': 80}, 'beyond_limit'),
    ({'elapsed': 30}, 'automatic_timeout'),
    ({'failed': True}, 'execution_failed'),
])
def test_only_capability_limit_timeout_or_failure_escalates_gas(kwargs, reason):
    """分别触发人工阈值、观察超时和执行失败，核验升级原因和人工处置标记。
    编写/修改日期（日志对应）：2026-10-12。
    """
    value = response(**kwargs)
    assert value['manual_required'] and reason in value['reasons']


def test_fire_keeps_automatic_protection_but_requires_manual_handling():
    """验证火灾仍执行保护且关闭普通风扇，信号回落后人工处置要求继续保留。
    编写/修改日期（日志对应）：2026-10-12。
    """
    value = response(kind='fire')
    assert value['manual_required'] and 'fire' in value['reasons']
    assert value['automatic_status'] == 'protection_reported'
    assert any(action['actuator'] == 'fan' and action['expected'] == 'off' for action in value['actions'])
    recovered = response(kind='fire', active=False, previous=value)
    assert recovered['manual_required']


def test_unknown_actuator_feedback_does_not_claim_automatic_success():
    """缺少执行器报告时只显示等待反馈，不能产生自动成功结论。
    编写/修改日期（日志对应）：2026-10-12。
    """
    value = evaluate_response('gas', True, 1, {'gas': 55}, {}, DEFAULT_RULES)
    assert value['automatic_status'] == 'awaiting_feedback'
    assert not any(action['matched'] for action in value['actions'])


def test_short_offline_recovery_only_leaves_alarm_to_confirm():
    """验证观察时限内恢复连接可继续自动处理，只保留报警待确认。
    编写/修改日期（日志对应）：2026-10-12。
    """
    waiting = response(kind='offline', elapsed=5)
    assert not waiting['manual_required']
    recovered = response(kind='offline', active=False, elapsed=10, previous=waiting)
    assert recovered['automatic_status'] == 'connection_recovered' and not recovered['manual_required']


def test_offline_beyond_reconnect_limit_requires_manual_inspection():
    """验证重连等待超出设置上限后升级现场连接核查。
    编写/修改日期（日志对应）：2026-10-12。
    """
    value = response(kind='offline', elapsed=30)
    assert value['manual_required'] and 'reconnect_timeout' in value['reasons']


def test_flame_is_not_masked_by_another_uncalibrated_channel():
    """验证其他传感器待标定不会屏蔽独立火焰信号，火灾和采样异常均保留。
    编写/修改日期（日志对应）：2026-10-12。
    """
    _, active = evaluate({'gas': None, 'smoke': None, 'temperature': None,
                          'flame': True, 'valid': False}, DEFAULT_RULES, {}, 0)
    assert 'fire' in active and 'sensor_fault' in active


def test_test_channel_recovery_distinguishes_calibration_from_fault():
    """验证完整测试通道允许判断燃气恢复，同时保留未标定告警。
    编写/修改日期（日志对应）：2026-10-12。
    """
    sample = {'gas': 70, 'smoke': 8, 'temperature': 25, 'flame': False, 'valid': False,
              'io_valid': True, 'transport': 'swd',
              'raw': {'gas_ao': 2866, 'smoke_ao': 328, 'temp_ao': 2048, 'flame_ao': 4095}}
    state, _ = evaluate(sample, DEFAULT_RULES, {}, 0)
    state, active = evaluate(sample, DEFAULT_RULES, state, 3)
    assert 'gas' in active
    sample['gas'] = 8
    state, _ = evaluate(sample, DEFAULT_RULES, state, 4)
    _, active = evaluate(sample, DEFAULT_RULES, state, 9)
    assert 'gas' not in active and 'sensor_fault' not in active
    sample['io_valid'] = False
    _, faulty = evaluate(sample, DEFAULT_RULES, {}, 10)
    assert 'sensor_fault' in faulty


def test_manual_limit_must_exceed_automatic_trigger():
    """验证 Pydantic 拒绝人工介入阈值不高于燃气报警值的配置。
    编写/修改日期（日志对应）：2026-10-12。
    """
    with pytest.raises(ValueError):
        RuleInput(revision=1, **{**DEFAULT_RULES, 'gas_manual_threshold': 40})


def test_confirming_alarm_does_not_clear_hazard_or_send_commands():
    """在隔离数据库验证确认不解除活动危险，处置完成需先恢复，且接口不下发开阀命令。
    编写/修改日期（日志对应）：2026-10-12。
    """
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        device = Device(id='stm32-001', name='test', location='test', token_hash='test', source='hardware')
        db.add(device)
        db.flush()
        alarm = Alarm(device_id=device.id, kind='fire', severity='critical', message='火焰测试',
                      evidence={'response': response(kind='fire')}, timeline=[])
        db.add(alarm)
        db.flush()
        user = SimpleNamespace(username='operator')
        acknowledge(alarm.id, NoteInput(note='已收到报警，正在核查'), user, db)
        assert alarm.status == 'active' and alarm.acknowledged_at
        with pytest.raises(HTTPException) as error:
            resolve_alarm(alarm.id, NoteInput(note='现场检查'), user, db)
        assert error.value.status_code == 409
        alarm.status, alarm.recovered_at = 'recovered', utcnow() + timedelta(seconds=5)
        view = resolve_alarm(alarm.id, NoteInput(note='现场核查完成，保持阀门关闭'), user, db)
        assert not view['response']['manual_required']
        assert view['response']['resolution']['by'] == 'operator'
        assert db.scalar(select(func.count()).select_from(Command)) == 0


def test_onsite_failure_escalates_even_after_signal_recovery_without_acknowledging():
    """验证现场报告舵机未动作时可升级人工，保留已恢复状态并且不自动确认报警。
    编写/修改日期（日志对应）：2026-10-12。
    """
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        device = Device(id='stm32-001', name='test', location='test', token_hash='test', source='hardware')
        db.add(device)
        db.flush()
        alarm = Alarm(device_id=device.id, kind='gas', severity='critical', message='燃气测试',
                      status='recovered', evidence={'response': response(active=False)}, timeline=[])
        db.add(alarm)
        db.flush()
        view = escalate_alarm(alarm.id, NoteInput(note='蜂鸣器正常，但舵机未转动'),
                              SimpleNamespace(username='operator'), db)
        assert view['response']['manual_required'] and 'onsite_issue' in view['response']['reasons']
        assert alarm.acknowledged_at is None and alarm.status == 'recovered'
        assert db.scalar(select(func.count()).select_from(Command)) == 0


@pytest.mark.parametrize('kind', ['gas', 'fire', 'sensor_fault', 'offline'])
def test_every_anomaly_survives_recovery_until_explicit_human_confirmation(kind):
    """修改日期（对应实习日志）：2026-10-12。回归验证四类异常恢复、重复发生、确认均有独立记录。
    """
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        device = Device(id='kitchen-001', name='test', location='test', token_hash='test', source='simulated',
                        latest={'gas': 8, 'smoke': 8, 'temperature': 25, 'valid': True},
                        actuators={'valve': 'closed', 'fan': 'off', 'buzzer': 'on'})
        db.add_all([device, RuleConfig(id=1, values=DEFAULT_RULES.copy())])
        db.flush()
        first = sync_alarm(db, device, kind, True, '测试异常')
        first_id = first.id
        db.commit()

        recovered = sync_alarm(db, device, kind, False, '')
        db.commit()
        db.expire_all()
        saved = db.get(Alarm, first_id)
        assert recovered.id == first_id and saved.status == 'recovered'
        assert saved.recovered_at and saved.acknowledged_at is None and saved.acknowledged_by is None
        assert any('异常记录继续保留，仍待人工确认' in item['message'] for item in saved.timeline)
        if kind == 'gas':
            assert saved.evidence['response']['automatic_status'] == 'auto_resolved'
            assert not saved.evidence['response']['manual_required']

        second = sync_alarm(db, device, kind, True, '再次发生异常')
        db.commit()
        assert second.id != first_id and db.scalar(select(func.count()).select_from(Alarm)) == 2
        acknowledge(first_id, NoteInput(note='已核查这次异常和自动响应记录'),
                    SimpleNamespace(username='operator'), db)
        db.commit()
        assert saved.acknowledged_by == 'operator' and saved.acknowledged_at
        assert db.get(Alarm, second.id).acknowledged_at is None

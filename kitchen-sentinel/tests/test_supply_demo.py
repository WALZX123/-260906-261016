"""文件职责：供气演示与既有安全监测的边界回归。
功能：验证工况准入、持续低值、锁存、恢复、人工处理和离线回放。
技术栈：pytest、SQLAlchemy SQLite、纯领域函数；关联MCU诊断协议、rules、response、replay。
编写/修改日期（日志对应）：2026-10-16。测试不操作现场设备。
"""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.core.db import Base
from backend.domain.rules import DEFAULT_RULES, evaluate
from backend.domain.response import evaluate_response
from backend.models import Device, Alarm, Telemetry
from backend.schemas import SampleInput, RuleInput
from backend.services.replay import archive_backfill


def sample(**changes):
    """提供开阀稳定后的有效低值演示基线，各用例显式覆盖门控条件。"""
    return {'gas': 5, 'smoke': 8, 'temperature': 25, 'flame': False, 'valid': True,
            'monitoring_enabled': True, 'actuators': {'valve': 'open'},
            'diagnostics': {'supply_demo_enabled': 1, 'supply_state': 3}, **changes}


@pytest.mark.parametrize('changes', [
    {'actuators': {'valve': 'closed'}}, {'monitoring_enabled': False},
    {'diagnostics': {'supply_state': 2}}, {'diagnostics': {}}, {'gas': 20},
])
def test_supply_not_evaluated_outside_stable_open(changes):
    """待机、关阀、稳定期、旧固件和正常值都不能产生供气低值事件。"""
    cfg = {**DEFAULT_RULES, 'supply_demo_enabled': True}
    state, _ = evaluate(sample(**changes), cfg, {}, 0)
    _, active = evaluate(sample(**changes), cfg, state, 30)
    assert 'supply_low' not in active


def test_supply_hold_latch_and_independent_recovery():
    """短时低值不触发，持续低值触发；关阀后锁存仍有效，独立复位后才经过恢复窗口。"""
    cfg = {**DEFAULT_RULES, 'supply_demo_enabled': True}
    state, active = evaluate(sample(), cfg, {}, 0)
    assert 'supply_low' not in active
    state, active = evaluate(sample(), cfg, state, 3)
    assert 'supply_low' in active
    latched = sample(actuators={'valve': 'closed'}, local_alarm='supply_low',
                     diagnostics={'supply_low_latched': 1, 'supply_state': 4})
    state, active = evaluate(latched, {**cfg, 'supply_demo_enabled': False}, state, 10)
    assert 'supply_low' in active
    state, active = evaluate(sample(gas=20), cfg, state, 11)
    assert 'supply_low' in active
    _, active = evaluate(sample(gas=20), cfg, state, 16)
    assert 'supply_low' not in active


def test_closed_valve_keeps_environment_gas_and_fire_monitoring():
    """供气不评估时仍接受燃气高值和本地火灾，不能因关阀屏蔽残余环境险情。"""
    s = sample(gas=80, flame=True, local_alarm='multiple', actuators={'valve': 'closed'})
    _, active = evaluate(s, DEFAULT_RULES, {}, 0)
    assert {'gas', 'fire'} <= active and 'supply_low' not in active


def test_supply_local_trip_immediate_and_requires_manual_handling():
    """MCU已完成持续低值判定，平台不重复等待；输出目标不包含排风，人工原因保留。"""
    s = sample(local_alarm='supply_low', diagnostics={'supply_low_latched': 1})
    _, active = evaluate(s, DEFAULT_RULES, {}, 0)
    assert 'supply_low' in active
    outputs = {'valve': 'closed', 'buzzer': 'on', 'power': 'on', 'fan': 'off'}
    response = evaluate_response('supply_low', True, 0, s, outputs, DEFAULT_RULES)
    assert response['manual_required'] and response['reasons'] == ['supply_issue']
    assert all(a['matched'] for a in response['actions'])
    assert evaluate_response('supply_low', False, 10, s, outputs, DEFAULT_RULES, response)['manual_required']


def test_supply_rule_range_and_offline_archive():
    """拒绝无正常区间的配置；离线故障重建待确认事件，并保存诊断以供查询。"""
    with pytest.raises(ValueError):
        RuleInput(revision=1, **{**DEFAULT_RULES, 'gas_threshold': 20})
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Device(id='supply-test', name='供气演示测试', location='test', source='hardware', token_hash='unused'))
        db.flush()
        p = SampleInput(boot_id='test-boot', sequence=1, sampled_at=datetime.now(timezone.utc),
                        **sample(local_alarm='supply_low', diagnostics={'supply_low_latched': 1},
                                 test_scenario='supply_low', backfilled=True))
        archive_backfill(db, 'supply-test', p)
        archive_backfill(db, 'supply-test', p)
        alarm = db.scalar(select(Alarm))
        assert alarm.kind == 'supply_low' and alarm.acknowledged_at is None
        assert alarm.evidence['response']['manual_required']
        assert db.scalar(select(Telemetry)).sample_context['diagnostics']['supply_low_latched'] == 1
    engine.dispose()

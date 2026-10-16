"""文件职责：完整存档、报告与离线回放的边界回归。
功能：验证分页完整性、按采集时间归属、补传幂等、报警保留及模型失败降级。
技术栈：pytest、SQLite、HTTPX MockTransport；关联archive、replay、expert，无真实控制输出。
编写/修改日期（日志对应）：2026-10-12、2026-10-15。
"""
from datetime import datetime, timezone, timedelta, date
from types import SimpleNamespace
import json
from decimal import Decimal
import httpx
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from backend.core.db import Base
from backend.models import Device, Telemetry, Alarm, ReplayState
from backend.schemas import SampleInput
from backend.api.archive import samples, period_bounds, report_facts
from backend.services.replay import archive_backfill, finish_replay
from backend.services import expert


def prepare():
    """创建独立数据库和现有在线设备，补传不得覆盖该实时状态。"""
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Device(id='real', name='测试', location='台架', source='hardware', token_hash='test',
        latest={'sequence': 900}, last_seen=datetime(2026, 10, 15, 12), actuators={'valve': 'open'}))
    db.flush()
    return db


def packet(sequence, alarm='normal'):
    """构造明确标记为补传的旧时刻样本，模拟校时后断线采样。"""
    return SampleInput(boot_id='mcu-10', sequence=sequence, sampled_at=datetime(2026, 10, 14, 2, tzinfo=timezone.utc)+timedelta(seconds=sequence),
        gas=65 if alarm == 'gas' else 16, smoke=8, temperature=25, flame=False, valid=False, io_valid=True,
        local_alarm=alarm, monitoring_enabled=True, transport='tcp', backfilled=True, clock_quality='device_synced')


def test_keyset_pagination_covers_every_matching_sample_by_acquisition_time():
    """按采集时间查出延迟入库的数据，固定快照翻完全部251条不重不漏。"""
    with prepare() as db:
        for i in range(251):
            p = packet(i)
            db.add(Telemetry(device_id='real', boot_id=p.boot_id, sequence=i, sampled_at=p.sampled_at.replace(tzinfo=None),
                received_at=datetime(2026, 10, 15), gas=16, smoke=8, temperature=25, flame=False, valid=False,
                sample_context={'monitoring_enabled': True, 'test_scenario': '', 'backfilled': True}))
        db.flush()
        found, before, ceiling = [], None, None
        while True:
            r = samples('real', datetime(2026, 10, 14, tzinfo=timezone.utc), datetime(2026, 10, 15, tzinfo=timezone.utc),
                'backfill', before, ceiling, 100, SimpleNamespace(), db)
            assert r['total'] == 251
            found += [v['id'] for v in r['items']]
            if not r['has_more']:
                break
            before, ceiling = r['next_before_id'], r['snapshot_id']
        assert len(found) == len(set(found)) == 251


def test_backfill_idempotency_and_recovery_preserve_unacknowledged_alarm():
    """离线气警及恢复只建一次事件；补传不更新在线时间或阀门当前状态。"""
    with prepare() as db:
        first = archive_backfill(db, 'real', packet(1, 'gas'))
        again = archive_backfill(db, 'real', packet(1, 'gas'))
        assert first['sample_id'] == again['sample_id'] and again['duplicate']
        archive_backfill(db, 'real', packet(2))
        db.flush()
        alarm = db.scalar(select(Alarm))
        assert alarm.status == 'recovered' and alarm.acknowledged_at is None
        assert alarm.evidence['backfilled'] and alarm.evidence['response']['manual_required']
        device = db.get(Device, 'real')
        assert device.latest['sequence'] == 900 and device.actuators['valve'] == 'open'
        assert device.last_seen == datetime(2026, 10, 15, 12)
        assert db.scalar(select(func.count()).select_from(Telemetry)) == 2


def test_replay_drain_closes_ongoing_offline_event_with_explicit_time_limit():
    """最后缓存仍报警但当前恢复，队列清空后仅标恢复上界，不自动确认。"""
    with prepare() as db:
        archive_backfill(db, 'real', packet(1, 'gas'))
        current = packet(20)
        current.diagnostics = {'cache_pending': 0}
        finish_replay(db, 'real', current)
        alarm = db.scalar(select(Alarm))
        assert alarm.status == 'recovered' and alarm.acknowledged_at is None
        assert '上界' in alarm.timeline[-1]['message']
        assert db.get(ReplayState, ('real', 'mcu-10')).active == {}


def test_report_calendar_and_full_aggregate():
    """自然周月按上海边界计算，完整聚合含补传且不按接收时间错分。"""
    start, end = period_bounds('monthly', date(2026, 10, 15))
    assert start == datetime(2026, 9, 30, 16) and end == datetime(2026, 10, 31, 16)
    first, last = period_bounds('weekly', date(2026, 10, 15))
    assert last-first == timedelta(days=7) and first == datetime(2026, 10, 11, 16)
    with prepare() as db:
        archive_backfill(db, 'real', packet(1, 'gas'))
        facts = report_facts(db, 'real', start, end)
        assert facts['window_start_local'] == '2026-10-01T00:00:00+08:00'
        assert facts['window_end_local_exclusive'] == '2026-11-01T00:00:00+08:00'
        assert facts['statistics']['sample_count'] == 1 and facts['statistics']['backfill_count'] == 1
        assert facts['faults'][0]['kind'] == 'gas'


def test_model_structured_output_and_rejected_invalid_json(monkeypatch):
    """只接受受约束的JSON结果；401和非法输出都明确降级，不伪造模型成功。"""
    monkeypatch.setattr(expert, 'settings', lambda: SimpleNamespace(model_api_key='test', model_base_url='https://provider.test', model_name='test-model'))
    original = httpx.Client
    content = {'summary': '证据不足', 'evidence': [], 'hypotheses': [], 'recommendations': ['检查记录'], 'uncertainties': ['没有标定']}
    for status, text, expected in [(200, json.dumps(content), 'succeeded'), (200, 'broken json', 'failed'), (401, '', 'failed')]:
        def respond(request):
            """验证提示词将输入隔离为证据，输出采用JSON模式。"""
            body = json.loads(request.content)
            assert body['response_format']['type'] == 'json_object'
            assert '低压生产实习台架' in body['messages'][0]['content']
            return httpx.Response(status, json={'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}]})
        monkeypatch.setattr(expert.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
        r = expert.expert_analysis({'sample_count': 0, 'mysql_sum': Decimal('3')}, '测试')
        assert r['model_status'] == expected
        assert (r['provider'] == 'test-model') == (expected == 'succeeded')

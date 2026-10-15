"""文件职责：平台路由、来源隔离与实时提交回归。
主要功能：验证转人工权限、Cookie/CSRF、响应前提交、完整报警计数及固件命令回执。
技术栈：pytest、FastAPI TestClient、SQLite StaticPool、HTTPX MockTransport。
模块联动：使用实际 API 路由及数据库事件，在隔离测试库中执行，绝不确认或修改现场报警。
编写/修改日期（日志对应）：2026-10-12、2026-10-13。
"""
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import auth, platform
from backend.core.db import Base, get_db
from backend.core.security import digest, hash_password
from backend.domain.rules import DEFAULT_RULES
from backend.models import Alarm, AuthSession, Command, Device, RuleConfig, User, utcnow
from backend.services.live import updates
from backend.services.monitoring import create_command, snapshot, record_command_outcome
from backend.domain.rules import evaluate
from gateway.swd_control import SwdCommands
from scripts.instance import ProjectInstance


@pytest.fixture
def isolated():
    """日志对应：2026-10-12。为实际路由提供共享内存测试库，每个请求独立提交或回滚。"""
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add_all([Device(id='real', name='实物', location='test', source='hardware', token_hash='test'),
                    Device(id='sim', name='模拟', location='test', source='simulated', token_hash='test'),
                    RuleConfig(id=1, values=DEFAULT_RULES.copy())])
        db.flush()
        db.add(Alarm(device_id='real', kind='gas', severity='critical', message='测试', timeline=[]))

    def database():
        """日志对应：2026-10-12。沿用响应前提交语义，让接口成功结果和数据库状态一致。"""
        with sessions.begin() as db:
            yield db

    app = FastAPI()
    app.include_router(auth.router, prefix='/api/v1')
    app.include_router(platform.router, prefix='/api/v1')
    app.dependency_overrides[get_db] = database
    yield TestClient(app), sessions
    engine.dispose()


@pytest.mark.parametrize('role,expected', [('admin', 200), ('operator', 200), ('viewer', 403)])
def test_escalate_route_permissions_and_csrf(isolated, role, expected):
    """日志对应：2026-10-12。经真实 POST 路由核验两种可写角色与只读拒绝，排除静态服务 405。"""
    client, sessions = isolated
    with sessions.begin() as db:
        user = User(username=role, password_hash='unused', role=role)
        db.add(user)
        db.flush()
        db.add(AuthSession(token_hash=digest('test-session'), user_id=user.id, csrf_token='test-csrf',
                           expires_at=utcnow() + timedelta(hours=1)))
    client.cookies.set('ks_session', 'test-session')
    payload = {'note': '测试现场执行异常，保持保护输出'}
    assert client.post('/api/v1/alarms/1/escalate', json=payload).status_code == 403
    response = client.post('/api/v1/alarms/1/escalate', json=payload, headers={'X-CSRF-Token': 'test-csrf'})
    assert response.status_code == expected
    if expected == 200:
        assert response.json()['response']['manual_required']
        with sessions() as db:
            saved = db.get(Alarm, 1)
            assert saved.evidence['response']['manual_required'] and saved.acknowledged_at is None


def test_login_session_is_committed_before_response(isolated):
    """日志对应：2026-10-12。登录返回后立即跨会话查库并写请求，不依赖延时补救提交竞态。"""
    client, sessions = isolated
    with sessions.begin() as db:
        db.add(User(username='login-test', role='operator', password_hash=hash_password('test-only-password')))
    result = client.post('/api/v1/auth/login', json={'username': 'login-test', 'password': 'test-only-password'})
    assert result.status_code == 200
    with sessions() as db:
        assert db.scalar(select(AuthSession)) is not None
    assert client.post('/api/v1/alarms/1/escalate', json={'note': '登录后立即操作'},
                       headers={'X-CSRF-Token': result.json()['csrf_token']}).status_code == 200


def test_hardware_scope_counts_old_unacknowledged_events(isolated):
    """日志对应：2026-10-13。超过一页的已恢复未确认异常仍纳入计数，模拟报警不混入正式页面。"""
    _, sessions = isolated
    with sessions.begin() as db:
        for i in range(110):
            db.add(Alarm(device_id='real', kind='gas', severity='critical', status='recovered',
                         message=str(i), timeline=[]))
        db.add(Alarm(device_id='sim', kind='fire', severity='critical', message='模拟', timeline=[]))
    with sessions() as db:
        value = snapshot(db, 'hardware')
        assert [d['id'] for d in value['devices']] == ['real']
        assert len(value['alarms']) == 100
        assert value['stats']['unacknowledged_alarms'] == 111
        assert value['stats']['active_alarms'] == 1
        assert all(a['device_id'] == 'real' for a in value['alarms'])


def test_only_committed_changes_wake_live_subscribers(isolated):
    """日志对应：2026-10-13。写入未提交、回滚及只读事务不能发布成功更新。"""
    _, sessions = isolated
    revision = updates.revision
    with sessions() as db:
        db.get(Device, 'real').name = '回滚修改'
        db.flush()
        assert updates.revision == revision
        db.rollback()
    assert updates.revision == revision
    with sessions.begin() as db:
        db.get(Device, 'real').name = '提交修改'
    assert updates.revision > revision


def test_capability_allows_only_online_supported_hardware_commands(isolated):
    """日志对应：2026-10-12。新固件在线且明确声明能力才创建实物命令，同一键保持幂等。"""
    _, sessions = isolated
    with sessions.begin() as db:
        device = db.get(Device, 'real')
        device.latest = {'control_capabilities': ['close_valve']}
        device.last_seen = utcnow()
        command = create_command(db, 'real', 'close_valve', 'test', 'test-command-key')
        assert create_command(db, 'real', 'close_valve', 'test', 'test-command-key').id == command.id


def test_swd_command_commits_action_before_sequence_and_retries_receipt():
    """日志对应：2026-10-12。模拟信箱检查提交顺序及回执重试，不接触真实硬件。"""
    class Target:
        """日志对应：2026-10-12。仅保存测试信箱和写入轨迹。"""
        def __init__(self):
            """日志对应：2026-10-12。初始化签名和空回执。"""
            self.words = [0x4348534B, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            self.writes = []

        def read_memory_block32(self, address, count):
            """日志对应：2026-10-12。返回当前构造信箱。"""
            return self.words.copy()

        def write32(self, address, value):
            """日志对应：2026-10-12。记录写入顺序并更新对应测试字段。"""
            self.writes.append(address)
            self.words[address // 4] = value

        def flush(self):
            """日志对应：2026-10-12。测试目标无需实际总线刷新。"""

    replies = []
    def handler(request):
        """日志对应：2026-10-12。第一次回执失败，第二次成功，检验不重复写执行器。"""
        if request.method == 'GET':
            return httpx.Response(200, json={'commands': [{'id': 'test-id', 'action': 'close_valve'}]})
        replies.append(request)
        return httpx.Response(503 if len(replies) == 1 else 200, json={})

    target = Target()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        bridge = SwdCommands(target, 0, http, 'http://test/device', 'test-token')
        bridge.step()
        assert target.writes == [12, 8]
        target.words[4:6] = [target.words[2], 1]
        with pytest.raises(httpx.HTTPStatusError):
            bridge.step()
        bridge.step()
        assert target.writes == [12, 8] and bridge.pending is None and len(replies) == 2


def test_failed_command_and_retry_remain_pending_human_confirmation(isolated):
    """日志对应：2026-10-12。独立控制失败必须成报警，重复回执不重复建档，重试成功仍待人工确认。"""
    _, sessions = isolated
    with sessions.begin() as db:
        command = Command(id='failed-command', device_id='real', action='close_valve', requested_by='test',
            idempotency_key='test-failed-command', expires_at=utcnow(), status='failed', result='测试执行故障')
        db.add(command)
        db.flush()
        record_command_outcome(db, command)
        record_command_outcome(db, command)
        alarms = list(db.scalars(select(Alarm).where(Alarm.kind == 'control_fault')))
        assert len(alarms) == 1 and alarms[0].acknowledged_at is None
        command.status = 'succeeded'
        record_command_outcome(db, command)
        assert alarms[0].status == 'recovered' and alarms[0].acknowledged_at is None
        assert alarms[0].evidence['response']['manual_required']


def test_local_danger_is_reported_without_second_hold_period():
    """日志对应：2026-10-13。平台对已经触发的本地保护不再额外等待，且待标定不屏蔽危险。"""
    _, active = evaluate({'gas': 70, 'smoke': 8, 'temperature': 25, 'valid': False,
                          'local_alarm': 'multiple', 'flame': False}, DEFAULT_RULES, {}, 0)
    assert {'gas', 'fire', 'sensor_fault'} <= active


def test_project_instance_prevents_parallel_start_and_releases_lock(tmp_path):
    """日志对应：2026-10-12。真实文件锁阻止同目录重复服务，失败的启动不删除已有运行记录。"""
    first, second = ProjectInstance(tmp_path), ProjectInstance(tmp_path)
    assert first.acquire()
    try:
        first.record('http://127.0.0.1:8000', 'hardware')
        assert not second.acquire()
        assert second.existing_url() == 'http://127.0.0.1:8000'
        second.release()
        assert (tmp_path / 'instance.json').is_file()
    finally:
        first.release()
    assert second.acquire()
    second.release()


def test_default_launch_uses_hardware_and_simulation_is_explicit(monkeypatch):
    """日志对应：2026-10-12。双击默认入口走实物，模拟模式必须显式选择，避免再启动另一套旧演示。"""
    import sys
    from start import parse_args
    monkeypatch.setattr(sys, 'argv', ['start.py'])
    assert parse_args().hardware
    monkeypatch.setattr(sys, 'argv', ['start.py', '--simulation'])
    assert not parse_args().hardware

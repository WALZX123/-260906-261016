"""文件职责：启用流程、待机采样边界及无线配置回归。
主要功能：确认待机不冒充测量、真实异常不因未标定被屏蔽、Wi-Fi 只能由可写角色在待机配置。
技术栈：pytest、FastAPI TestClient、SQLite；模块联动：规则、FrameBuilder、wifi API。
编写/修改日期（日志对应）：2026-10-12、2026-10-15。
"""
import json
from datetime import timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.api import wifi
from backend.core.db import Base, get_db
from backend.domain.rules import DEFAULT_RULES, evaluate
from backend.models import Device, User, AuthSession, utcnow
from backend.core.security import digest
from gateway.swd import FrameBuilder


def test_standby_heartbeat_has_no_measurements_and_does_not_trip_fault():
    """待机心跳必须保留能力和输出，隐藏停采后的旧值；无效值不会制造待机报警。日期：2026-10-15。"""
    board = dict(sequence=8, uptime_ms=9000, monitoring_enabled=0, sample_count=0, version=5,
        smoke_raw=1200, temp_raw=2200, gas_raw=4095, flame_raw=3000, flame_do=0, smoke_do=0,
        servo_pulse_us=500, gpio_a_output=0, gpio_b_output=0, hazard_flags=0, control_capabilities=65535)
    sample = FrameBuilder().build(board)
    assert sample['monitoring_enabled'] is False and 'gas' not in sample
    assert sample['actuators']['valve'] == 'closed' and 'start_monitoring' in sample['control_capabilities']
    _, active = evaluate(sample, DEFAULT_RULES, {}, 10)
    assert active == set()


def test_tcp_hardware_keeps_alarm_and_quality_semantics():
    """无线和 SWD 采用同一相对指标规则，未标定与无效采样严格分开。日期：2026-10-15。"""
    sample = dict(valid=False, io_valid=True, transport='tcp', monitoring_enabled=True,
        gas=20, smoke=50, temperature=25, flame=False, local_alarm='fire', test_scenario='smoke',
        raw=dict(gas_ao=800, smoke_ao=100, temp_ao=2000, flame_ao=4000))
    _, active = evaluate(sample, DEFAULT_RULES, {}, 10)
    assert active == {'fire'}
    sample.update(io_valid=False, local_alarm='normal', smoke=10)
    _, active = evaluate(sample, DEFAULT_RULES, {}, 11)
    assert active == {'sensor_fault'}


def test_wifi_credentials_are_write_only_and_viewer_cannot_configure(tmp_path, monkeypatch):
    """实路由核验只读拒绝、操作员待机写入和运行期间拒绝；响应与审计都不泄露密码。日期：2026-10-15。"""
    path = tmp_path / 'wifi.json'
    monkeypatch.setattr(wifi, 'CONFIG', path)
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        user = User(username='operator', password_hash='unused', role='operator')
        viewer = User(username='viewer', password_hash='unused', role='viewer')
        db.add_all([user, viewer, Device(id='real', name='real', location='bench', source='hardware',
                                       token_hash='unused', latest={'monitoring_enabled': False})])
        db.flush()
        for person in [user, viewer]:
            db.add(AuthSession(token_hash=digest(person.username), user_id=person.id,
                csrf_token='csrf', expires_at=utcnow() + timedelta(hours=1)))

    def database():
        """每个接口请求独立提交事务，测试不使用真实项目数据库。"""
        with sessions.begin() as db:
            yield db

    app = FastAPI()
    app.include_router(wifi.router)
    app.dependency_overrides[get_db] = database
    client = TestClient(app)
    payload = {'ssid': 'bench', 'password': 'private-test-password', 'host': '192.168.43.10'}
    client.cookies.set('ks_session', 'viewer')
    assert client.post('/wifi', json=payload, headers={'X-CSRF-Token': 'csrf'}).status_code == 403
    client.cookies.set('ks_session', 'operator')
    response = client.post('/wifi', json=payload, headers={'X-CSRF-Token': 'csrf'})
    assert response.status_code == 200
    assert payload['password'] not in response.text and 'token' not in response.json()
    assert 'password' not in client.get('/wifi').json()
    assert json.loads(path.read_text())['password'] == payload['password']
    with sessions.begin() as db:
        db.get(Device, 'real').latest = {'monitoring_enabled': True}
    assert client.post('/wifi', json=payload, headers={'X-CSRF-Token': 'csrf'}).status_code == 409
    engine.dispose()

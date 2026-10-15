"""文件职责：低压模型的五类险情与分项执行器验收。
主要功能：经 Wi-Fi 下发演练，核对保护输出、自然到期、报警留档和恢复开阀，保存实际回执。
技术栈：HTTPX、轮询断言、JSON；模块联动：设备启用、MCU、历史与报警接口。
编写/修改日期（日志对应）：2026-10-09、2026-10-12、2026-10-15。运行会操作已连接低压模型。
"""
import json
import time
from datetime import datetime
from uuid import uuid4
import httpx
from backend.core.config import settings, PROJECT_ROOT
from scripts.check_realtime_system import exercise


def main():
    """使用真实设备命令核对五种保护组合，十五秒演练自然结束后仍保留未确认事件。"""
    cfg = settings()
    evidence = {'started_at': datetime.now().astimezone().isoformat(), 'scenarios': [], 'outputs': []}
    with httpx.Client(base_url='http://127.0.0.1:8000', trust_env=False, timeout=10) as client:
        login = client.post('/api/v1/auth/login', json={'username': cfg.admin_username, 'password': cfg.admin_password})
        login.raise_for_status()
        client.headers['X-CSRF-Token'] = login.json()['csrf_token']

        def snapshot():
            """取得正式节点的真实状态与未确认事件。"""
            result = client.get('/api/v1/snapshot')
            result.raise_for_status()
            return result.json()

        def command(action):
            """等候 MCU 回执，失败立即停止测试，不伪造或重写既有回执。"""
            result = client.post('/api/v1/devices/stm32-001/commands',
                json={'action': action, 'idempotency_key': uuid4().hex})
            result.raise_for_status()
            command_id = result.json()['id']
            end = time.monotonic() + 16
            while time.monotonic() < end:
                row = next(c for c in snapshot()['commands'] if c['id'] == command_id)
                if row['status'] in ('succeeded', 'failed', 'timeout'):
                    assert row['status'] == 'succeeded', row
                    return row
                time.sleep(.3)
            raise RuntimeError(action + ' missing MCU receipt')

        def wait_for(predicate, seconds=12):
            """按状态等待，收集真实设备传输来源，避免把延时本身当验证。"""
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                device = snapshot()['devices'][0]
                if predicate(device):
                    return device
                time.sleep(.3)
            raise AssertionError(snapshot()['devices'][0])

        try:
            initial = wait_for(lambda d: d['online'] and d['latest']['transport'] == 'tcp', 40)
            if not initial['latest']['monitoring_enabled']:
                command('start_monitoring')
            wait_for(lambda d:d['latest']['diagnostics']['arming'] == 0)
            if snapshot()['devices'][0]['actuators']['valve'] != 'open':
                command('open_valve')
            for name in ('gas', 'smoke', 'temperature', 'flame', 'multiple'):
                created = command('inject_' + name)
                device = wait_for(lambda d:d['latest']['test_scenario'] == name and d['actuators']['buzzer'] == 'on')
                expected = {'valve': 'closed', 'buzzer': 'on', 'power': 'on', 'fan': 'on' if name == 'gas' else 'off'}
                assert device['actuators'] == expected
                assert device['latest']['transport'] == 'tcp'
                record = {'scenario': name, 'command': created, 'device': device, 'expected': expected,
                          'physical_motion_verified': False}
                history = client.get('/api/v1/telemetry?device_id=stm32-001&limit=5').json()
                assert any(s.get('test_scenario') == name and s.get('raw') for s in history)
                if name == 'smoke':
                    # 该项不发送取消，实际等待 MCU 的十五秒截止，证明网页断开后也不会永久注入。
                    wait_for(lambda d:not d['latest']['test_scenario'], 20)
                    record['natural_expiry_verified'] = True
                else:
                    record['cancel'] = command('cancel_injection')
                wait_for(lambda d:not d['latest']['test_scenario'] and d['actuators']['buzzer'] == 'off')
                assert snapshot()['devices'][0]['actuators']['valve'] == 'closed'
                time.sleep(5.5)
                alarms = [a for a in snapshot()['alarms'] if a['evidence'].get('test_scenario') == name]
                assert alarms and any(a['status'] == 'recovered' and a['acknowledged_at'] is None for a in alarms)
                record['alarm_ids'] = [a['id'] for a in alarms]
                record['rearm'] = command('open_valve')
                wait_for(lambda d:d['actuators']['valve'] == 'open')
                evidence['scenarios'].append(record)
                print(name, 'protection, history and unacknowledged recovery verified', flush=True)
            for action in ('self_test', 'test_buzzer', 'test_fan', 'test_relay', 'test_servo'):
                record = exercise(client, action)
                evidence['outputs'].append(record)
                print(action, record['status'], flush=True)
            command('open_valve')
            command('stop_monitoring')
            evidence['final'] = wait_for(lambda d:not d['latest']['monitoring_enabled'])
            evidence['all_passed'] = True
        finally:
            client.post('/api/v1/auth/logout')
            evidence['finished_at'] = datetime.now().astimezone().isoformat()
            (PROJECT_ROOT / '.runtime/hardware-test/wifi_scenarios_acceptance_20261015.json').write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

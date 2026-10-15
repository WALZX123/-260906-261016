"""文件职责：实机实时服务和命令回执验收。
主要功能：检查权限接口、实物来源隔离、实时帧时延、固件规则同步，显式开启时测试短时执行器输出。
技术栈：Python、HTTPX、WebSocket、单调计时、JSON 证据。
模块联动：调用实际运行 API 与 SWD 网关；不确认或处置真实报警，输出读回不能代替现场机械验收。
编写/修改日期（日志对应）：2026-10-12、2026-10-13、2026-10-15。
"""
import argparse
import json
import time
from datetime import datetime
from math import ceil
from uuid import uuid4

import httpx
from websockets.sync.client import connect

from backend.core.config import PROJECT_ROOT, settings


def snapshot(client):
    """日志对应：2026-10-12。取得正式实物快照，接口错误立即停止验收。"""
    response = client.get('/api/v1/snapshot')
    response.raise_for_status()
    return response.json()


def exercise(client, action):
    """日志对应：2026-10-12。逐项发命令并观察六秒回执和输出；险情存在则不发分项测试。"""
    data = snapshot(client)
    device = data['devices'][0]
    if action.startswith('test_') and device['latest']['local_alarm'] not in ('normal', 'sensor_fault'):
        return {'action': action, 'skipped': '现场存在危险信号，保留自动保护'}
    response = client.post('/api/v1/devices/' + device['id'] + '/commands',
                           json={'action': action, 'idempotency_key': 'acceptance-' + uuid4().hex})
    response.raise_for_status()
    command_id = response.json()['id']
    records, command = [], response.json()
    started = time.monotonic()
    while time.monotonic() - started < 6:
        time.sleep(.4)
        value = snapshot(client)
        command = next((c for c in value['commands'] if c['id'] == command_id), command)
        device = value['devices'][0]
        records.append({'at': datetime.now().astimezone().isoformat(), 'outputs': device['actuators'],
                        'diagnostics': device['latest'].get('diagnostics', {})})
    result = {'action': action, 'command_id': command_id, 'status': command['status'],
              'result': command.get('result'), 'observations': records, 'physical_motion_verified': False}
    if command['status'] != 'succeeded':
        raise RuntimeError('命令未收到成功回执：' + json.dumps(result, ensure_ascii=False))
    return result


def main():
    """日志对应：2026-10-12。默认只读核验，--exercise-outputs 显式启用低压台架短时输出。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--exercise-outputs', action='store_true')
    args = parser.parse_args()
    cfg, base = settings(), args.url.rstrip('/')
    evidence = {'checked_at': datetime.now().astimezone().isoformat(), 'commands': []}
    with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
        login = client.post('/api/v1/auth/login', json={'username': cfg.admin_username, 'password': cfg.admin_password})
        login.raise_for_status()
        client.headers['X-CSRF-Token'] = login.json()['csrf_token']
        try:
            probe = client.post('/api/v1/alarms/2147483647/escalate', json={'note': '不存在记录的路由检查，不修改现场事件'})
            assert probe.status_code == 404
            evidence['escalate_route'] = probe.status_code
            data = snapshot(client)
            assert all(d['source'] == 'hardware' for d in data['devices'])
            device = data['devices'][0]
            assert device['online'] and device['firmware'] == 'stm32f103-hwtest/5.0'
            diagnostics = device['latest']['diagnostics']
            assert diagnostics['rules_revision'] == data['rules']['revision']
            assert diagnostics['gas_threshold'] == ceil(data['rules']['gas_threshold'])
            assert diagnostics['smoke_threshold'] == ceil(data['rules']['smoke_threshold'])
            assert diagnostics['temperature_threshold_centi'] == round(data['rules']['temperature_threshold'] * 100)
            evidence.update(device=device['id'], firmware=device['firmware'], diagnostics=diagnostics,
                            source_isolation=True, rules_synchronized=True)
            cookie = '; '.join(key + '=' + value for key, value in client.cookies.items())
            url = base.replace('http://', 'ws://').replace('https://', 'wss://') + '/api/v1/live'
            with connect(url, origin=base, additional_headers={'Cookie': cookie}, proxy=None) as ws:
                first = json.loads(ws.recv(timeout=6))
                frames, gaps = [first], []
                before = time.monotonic()
                for _ in range(5):
                    frame = json.loads(ws.recv(timeout=4))
                    now = time.monotonic()
                    gaps.append(round(now - before, 3))
                    before = now
                    frames.append(frame)
                assert frames[-1]['devices'][0]['latest']['sequence'] > first['devices'][0]['latest']['sequence']
                evidence['websocket_intervals_seconds'] = gaps
                evidence['websocket_sequence_start'] = first['devices'][0]['latest']['sequence']
                evidence['websocket_sequence_end'] = frames[-1]['devices'][0]['latest']['sequence']
            if args.exercise_outputs:
                for action in ('self_test', 'test_buzzer', 'test_fan', 'test_relay', 'test_servo'):
                    result = exercise(client, action)
                    evidence['commands'].append(result)
                    print(action, result.get('status', result.get('skipped')), flush=True)
        finally:
            client.post('/api/v1/auth/logout')
            filename = 'wifi_outputs_acceptance_20261015.json' if args.exercise_outputs else 'wifi_service_check_20261015.json'
            path = PROJECT_ROOT / '.runtime/hardware-test' / filename
            path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in evidence.items() if key != 'commands'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

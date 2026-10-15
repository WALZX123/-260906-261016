"""文件职责：实物数据到 PC 的链路核验。
主要功能：临时登录，检查快照、历史、来源标记、固件控制能力和 WebSocket，不操作执行器。
技术栈：Python、HTTPX、WebSocket、JSON。
模块联动：访问后端认证与平台接口，读取本机测试账号并在结束时注销；只输出检查结果，不输出凭据。
编写/修改日期（日志对应）：2026-10-12；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""
from __future__ import annotations

import argparse
import json

import httpx
from websockets.sync.client import connect

from backend.core.config import PROJECT_ROOT, settings


def main() -> None:
    """使用本机账号建立临时会话，检查完成后注销该会话。
    编写/修改日期（日志对应）：2026-10-12。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    base = args.url.rstrip('/')
    cfg = settings()
    result = {}
    with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
        response = client.post('/api/v1/auth/login', json={
            'username': cfg.admin_username, 'password': cfg.admin_password,
        })
        response.raise_for_status()
        client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        try:
            health = client.get('/api/health')
            health.raise_for_status()
            result['health'] = health.json()['status']
            view = client.get('/api/v1/snapshot')
            view.raise_for_status()
            hardware = view.json()['devices'][0]
            assert hardware['id'] == 'stm32-001' and hardware['source'] == 'hardware'
            assert hardware['online'] and hardware['latest']['transport'] == 'swd'
            assert hardware['latest']['raw'] and not hardware['latest']['valid']
            # 日志对应：2026-09-22。新版温度为标称公式估算，量程异常时允许空值。
            temperature = hardware['latest'].get('temperature')
            assert temperature is None or -20 <= temperature <= 80
            result.update(device=hardware['id'], online=hardware['online'],
                          transport=hardware['latest']['transport'], raw=hardware['latest']['raw'],
                          temperature_estimate_c=temperature, filtered=hardware['latest'].get('filtered'))
            history = client.get('/api/v1/telemetry', params={'limit': 5})
            history.raise_for_status()
            rows = history.json()
            assert rows and all(row['device_id'] == hardware['id'] for row in rows)
            result['history_rows_checked'] = len(rows)
            # 日志对应：2026-10-12。只检查实机能力声明，分项执行器测试由专门入口显式发起。
            result['control_capabilities'] = hardware['latest'].get('control_capabilities', [])
            result['diagnostics'] = hardware['latest'].get('diagnostics', {})
            system = client.get('/api/v1/system')
            system.raise_for_status()
            assert 'SWD' in system.json()['hardware']
            result['system_hardware'] = system.json()['hardware']
            # 同一登录会话检查 WebSocket 推送，Cookie 仅在进程内使用。
            socket_url = base.replace('http://', 'ws://').replace('https://', 'wss://') + '/api/v1/live'
            cookie = '; '.join(f'{key}={value}' for key, value in client.cookies.items())
            with connect(socket_url, origin=base, additional_headers={'Cookie': cookie},
                         proxy=None, open_timeout=10) as socket:
                live = json.loads(socket.recv(timeout=6))
                assert live['devices'][0]['id'] == hardware['id']
                result['websocket'] = 'ok'
                result['live_sequence'] = live['devices'][0]['latest']['sequence']
            # 保存具体检查结果，便于将实机证据与单元测试结果分别追溯。
            path = PROJECT_ROOT / '.runtime' / 'hardware-test' / 'pipeline_check.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            client.post('/api/v1/auth/logout')


if __name__ == '__main__':
    main()

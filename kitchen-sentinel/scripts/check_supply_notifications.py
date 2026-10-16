"""文件职责：供气工况与账号通知的实机验收。
功能：经Wi-Fi验证持续低值保护、锁存、独立复位、关阀后环境采样和数据库偏好恢复。
技术栈：HTTPX、状态轮询、JSON证据；关联真实STM32、FastAPI及个人提醒接口。
编写/修改日期（日志对应）：2026-10-16。运行会操作已连接的低压台架，不代签报警确认。
"""
import json
import time
from datetime import datetime
from uuid import uuid4
import httpx
from backend.core.config import settings, PROJECT_ROOT


def main():
    """危险或回执异常即终止；每一步保存实际时间，保留既有现场报警。"""
    cfg = settings()
    evidence = {'started_at': datetime.now().astimezone().isoformat()}
    with httpx.Client(base_url='http://127.0.0.1:8000', trust_env=False, timeout=10) as c:
        def login():
            """仅使用本机环境账号，不输出凭据或会话。"""
            r = c.post('/api/v1/auth/login', json={'username': cfg.admin_username, 'password': cfg.admin_password})
            r.raise_for_status()
            c.headers['X-CSRF-Token'] = r.json()['csrf_token']

        def snapshot():
            """读取正式节点的事务提交结果。"""
            r = c.get('/api/v1/snapshot?scope=hardware')
            r.raise_for_status()
            return r.json()

        def device():
            """定位实物而不是模拟节点。"""
            return next(d for d in snapshot()['devices'] if d['id'] == 'stm32-001')

        def wait(predicate, seconds=20):
            """根据实机状态等待；超时抛出简明状态，凭据不会进入日志。"""
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                d = device()
                if predicate(d):
                    return d
                time.sleep(.35)
            raise AssertionError({'timeout': True, 'device': d})

        def command(action):
            """提交幂等动作并等待真实MCU回执，入队成功不能当作执行成功。"""
            r = c.post('/api/v1/devices/stm32-001/commands', json={'action': action, 'idempotency_key': uuid4().hex})
            r.raise_for_status()
            identity, end = r.json()['id'], time.monotonic() + 18
            while time.monotonic() < end:
                row = next(x for x in snapshot()['commands'] if x['id'] == identity)
                if row['status'] in ('succeeded', 'failed', 'timeout'):
                    assert row['status'] == 'succeeded', row
                    return row
                time.sleep(.35)
            raise AssertionError('未收到固件回执：' + action)

        login()
        try:
            preferences = '/api/v1/auth/notification-preferences'
            saved = {'sound_enabled': True, 'desktop_enabled': True}
            r = c.put(preferences, json=saved)
            r.raise_for_status()
            c.post('/api/v1/auth/logout').raise_for_status()
            login()
            assert c.get(preferences).json() == saved
            evidence['preferences_after_relogin'] = saved
            s = snapshot()
            rules = s['rules']
            # 供气演示必须显式配置，不为通过测试降低既有环境报警阈值。
            if not rules['supply_demo_enabled']:
                r = c.put('/api/v1/rules', json={**rules, 'supply_demo_enabled': True})
                r.raise_for_status()
            d = wait(lambda d: d['online'] and d['firmware'] == 'stm32f103-hwtest/7.0')
            if not d['latest']['monitoring_enabled']:
                command('start_monitoring')
            d = wait(lambda d: not d['latest']['diagnostics'].get('arming'))
            assert rules['supply_low_threshold'] <= d['latest']['gas'] < rules['gas_threshold'], '请将电位器置于正常演示范围'
            assert d['latest']['local_alarm'] in ('normal', 'supply_low'), '真实环境险情优先，停止演练'
            if d['actuators']['valve'] == 'closed':
                command('open_valve')
            evidence['baseline'] = wait(lambda d: d['latest']['diagnostics'].get('supply_state') == 3)
            evidence['low_command'] = command('inject_supply_low')
            d = wait(lambda d: d['latest']['diagnostics'].get('supply_low_latched') == 1)
            assert d['actuators'] == {'valve': 'closed', 'buzzer': 'on', 'power': 'on', 'fan': 'off'}
            assert d['latest']['gas'] >= rules['supply_low_threshold'], '供气注入不得改写环境燃气数值'
            evidence['protected'] = d
            evidence['cancel'] = command('cancel_injection')
            time.sleep(6)
            d = device()
            assert d['latest']['diagnostics']['supply_low_latched'] == 1 and d['actuators']['valve'] == 'closed'
            alarms = [a for a in snapshot()['alarms'] if a['kind'] == 'supply_low' and a['status'] == 'active']
            assert alarms and all(a['response']['manual_required'] and a['acknowledged_at'] is None for a in alarms)
            evidence['latched_after_cancel'] = d
            evidence['alarm_ids'] = [a['id'] for a in alarms]
            evidence['independent_reset'] = command('open_valve')
            evidence['settling_after_reset'] = wait(lambda d: d['latest']['diagnostics'].get('supply_state') == 2)
            wait(lambda d: d['latest']['diagnostics'].get('supply_state') == 3)
            time.sleep(rules['recovery_seconds'] + 1)
            rows = [a for a in snapshot()['alarms'] if a['id'] in evidence['alarm_ids']]
            assert rows and all(a['status'] == 'recovered' and a['acknowledged_at'] is None for a in rows)
            evidence['recovered_pending_confirmation'] = rows
            command('close_valve')
            before = device()
            time.sleep(5)
            after = device()
            assert after['latest']['diagnostics']['sample_count'] > before['latest']['diagnostics']['sample_count']
            assert after['latest']['raw'] and after['latest']['diagnostics']['supply_state'] == 1
            assert after['latest']['diagnostics']['supply_low_latched'] == 0
            evidence['closed_valve_environment_sampling'] = after
            command('open_valve')
            evidence['final'] = wait(lambda d: d['latest']['diagnostics'].get('supply_state') == 3)
            evidence['all_passed'] = True
            print('Supply low protection, latch, independent reset, environment sampling and preference persistence passed', flush=True)
        finally:
            c.post('/api/v1/auth/logout')
            evidence['finished_at'] = datetime.now().astimezone().isoformat()
            path = PROJECT_ROOT / '.runtime/hardware-test/supply_notifications_20261016.json'
            path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

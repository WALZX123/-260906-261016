"""文件职责：验证实际设备启用、限时险情演练及受控恢复。
主要功能：检查待机停采、正常开阀、烟雾保护、命令回执、恢复留档和读写权限。
技术栈：HTTPX、真实设备 API、JSON 证据；模块联动：运行中的后端和 MCU。
编写/修改日期（日志对应）：2026-10-12、2026-10-15。此脚本会操作低压模型执行器。
"""
import json
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import httpx
from backend.core.config import settings


def main():
    """先启用基线，再演练烟雾并核对火灾策略，取消后恢复开阀；所有事件保持未确认。"""
    config = settings()
    evidence = {'started_at': datetime.now().astimezone().isoformat(), 'steps': []}
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=10, trust_env=False) as client:
        login = client.post('/api/v1/auth/login', json={'username': config.admin_username, 'password': config.admin_password})
        login.raise_for_status()
        headers = {'X-CSRF-Token': login.json()['csrf_token']}

        def snapshot():
            """读取正式实物快照；不将 SQL 或 RAM 人为改动冒充设备动作。"""
            result = client.get('/api/v1/snapshot')
            result.raise_for_status()
            return result.json()

        def state():
            """取真实节点，返回的 actuators 是输出报告，机械运动需另行现场核对。"""
            return next(d for d in snapshot()['devices'] if d['source'] == 'hardware')

        def command(action):
            """等待实际固件回执，拒绝/超时直接报错并保留证据；不修改回执或报警状态。"""
            device = state()
            result = client.post('/api/v1/devices/'+device['id']+'/commands', headers=headers,
                                 json={'action': action, 'idempotency_key': uuid4().hex})
            result.raise_for_status()
            created = result.json()
            deadline = time.monotonic()+22
            while time.monotonic() < deadline:
                view = snapshot()
                row = next(c for c in view['commands'] if c['id'] == created['id'])
                if row['status'] in ('succeeded','failed','timeout'):
                    evidence['steps'].append({'action': action, 'command': row, 'device': state()})
                    print(action, row['status'], flush=True)
                    assert row['status'] == 'succeeded', row
                    return
                time.sleep(.4)
            raise RuntimeError('command receipt did not arrive: '+action)

        def until(predicate, seconds=12):
            """在有界时间内等待实际状态满足条件，避免固定延时掩盖响应故障。"""
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                device = state()
                if predicate(device):
                    return device
                time.sleep(.4)
            raise AssertionError(state())

        try:
            before = until(lambda d:d['online'] and d['latest'].get('transport') == 'tcp', 40)
            evidence['initial'] = before
            assert before['latest']['monitoring_enabled'] is False
            count = before['latest']['diagnostics']['sample_count']
            time.sleep(1.5)
            assert state()['latest']['diagnostics']['sample_count'] == count
            command('start_monitoring')
            normal = until(lambda d:d['latest']['diagnostics']['arming']==0 and d['actuators']['valve']=='open')
            assert normal['actuators']['fan'] == 'off'
            evidence['normal'] = normal
            command('inject_smoke')
            alarm = until(lambda d:d['latest']['test_scenario']=='smoke' and d['actuators']['valve']=='closed')
            assert alarm['actuators'] == {'valve':'closed','fan':'off','power':'on','buzzer':'on'}
            events = [a for a in snapshot()['alarms'] if a['kind']=='fire' and a['evidence'].get('test_scenario')=='smoke']
            assert events and events[0]['response']['manual_required'] and events[0]['acknowledged_at'] is None
            evidence['smoke_alarm'] = events[0]
            # 经真实写接口验证转人工，不把自动恢复或操作本身当成人员确认。
            result = client.post('/api/v1/alarms/'+str(events[0]['id'])+'/escalate', headers=headers,
                                 json={'note':'2026-10-15 低压模型烟雾注入联动核验，输出符合策略；记录转人工待现场核对'})
            result.raise_for_status()
            evidence['escalation_http_status'] = result.status_code
            command('cancel_injection')
            until(lambda d:not d['latest']['test_scenario'] and d['actuators']['buzzer']=='off')
            assert state()['actuators']['valve']=='closed'
            time.sleep(6)
            recovered = next(a for a in snapshot()['alarms'] if a['id']==events[0]['id'])
            assert recovered['status']=='recovered' and recovered['acknowledged_at'] is None
            evidence['recovered_alarm'] = recovered
            command('open_valve')
            evidence['rearmed'] = until(lambda d:d['actuators']['valve']=='open')
            command('stop_monitoring')
            evidence['final_standby'] = until(lambda d:not d['latest']['monitoring_enabled'])
        finally:
            client.post('/api/v1/auth/logout', headers=headers)
            evidence['finished_at'] = datetime.now().astimezone().isoformat()
            path = Path('.runtime/hardware-test/activation_acceptance_20261015.json')
            path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Lifecycle and smoke protection verified; physical motion not inferred from output registers')


if __name__ == '__main__':
    main()

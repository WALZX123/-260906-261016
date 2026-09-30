"""独立的虚拟边缘控制器。

模拟器故意通过和真实设备相同的控制拉取、规则计算、遥测上报流程工作，
这样中期演示可以覆盖设备离线、重试、幂等和命令回执，而不是直接修改数据库。
"""
import argparse
import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# 允许直接执行 `python simulator/main.py`。
# Python 直接运行文件时只把 simulator 目录加入 sys.path，项目根目录需要手动补上。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402
from backend.core.config import settings  # noqa: E402
from backend.domain.rules import DEFAULT_RULES, evaluate  # noqa: E402

SCENARIOS = ('normal', 'gas', 'fire', 'spike', 'sensor_fault', 'offline', 'command_timeout')


def load_state(path: Path) -> tuple[dict, dict]:
    """读取本地执行状态；文件损坏时备份并从安全初始状态恢复。"""

    if not path.exists():
        return {}, {}
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(saved, dict):
            raise ValueError('状态文件根节点不是对象')
        actuators = saved.get('actuators', {})
        completed = saved.get('completed', {})
        if not isinstance(actuators, dict) or not isinstance(completed, dict):
            raise ValueError('状态文件字段类型不正确')
        return actuators, completed
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        backup = path.with_suffix(path.suffix + '.broken')
        try:
            path.replace(backup)
        except OSError:
            # 备份失败也不能阻止模拟器恢复运行，后续会重新写入状态文件。
            pass
        logging.warning('edge state reset: %s (%s)', path, exc)
        return {}, {}


def save_state(path: Path, payload: dict) -> None:
    """原子保存状态，避免程序中断时留下半截 JSON。"""

    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
    except OSError as exc:
        logging.warning('edge state could not be saved: %s', exc)


def generate(scenario, elapsed, sequence):
    """根据演示场景生成一组带边界的传感器采样。"""
    gas = 8 + math.sin(sequence / 6) * 1.8
    smoke = 6 + math.cos(sequence / 8) * 1.5
    temperature = 25 + math.sin(sequence / 13) * 0.6
    flame = False
    valid = scenario != 'sensor_fault'
    if scenario == 'gas':
        gas = min(82, 8 + elapsed * 5)
    elif scenario == 'fire':
        smoke = min(88, 6 + elapsed * 6)
        temperature = min(92, 25 + elapsed * 4)
        flame = elapsed > 12
    elif scenario == 'spike' and 4 < elapsed < 6:
        gas = 70
    return {'gas': round(gas, 2) if valid else None, 'smoke': round(smoke, 2),
            'temperature': round(temperature, 2), 'flame': flame, 'valid': valid}


def main():
    """运行设备主循环；网络中断时继续本地计算和保护动作。"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--device', default='kitchen-001')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    base = args.url + '/api/v1/ingest/devices/' + args.device
    runtime = PROJECT_ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    state_file = runtime / f'{args.device}-edge-state.json'
    state = {}
    actuators = {'valve': 'open', 'fan': 'off', 'power': 'on', 'buzzer': 'off'}
    completed = {}
    saved_actuators, saved_completed = load_state(state_file)
    actuators.update(saved_actuators)
    completed = saved_completed
    rules = DEFAULT_RULES.copy()
    revision, scenario = -1, 'normal'
    start = time.monotonic()
    boot, sequence = str(uuid4()), 0
    silenced_until = 0
    # 模拟器按真实设备的节奏工作：先拉取规则和控制命令，再采样、计算本地状态、上报。
    # 后端停机时仍会写入 .runtime 中的最后状态，便于观察“断网仍保护”的行为。
    with httpx.Client(headers={'Authorization': 'Bearer ' + settings().device_token}, timeout=3) as client:
        while True:
            cycle = time.monotonic()
            try:
                response = client.get(base + '/control')
                response.raise_for_status()
                control = response.json()
                rules = control['rules']
                if control['scenario_revision'] != revision:
                    scenario, revision, start = control['scenario'], control['scenario_revision'], cycle
                    logging.info('scenario=%s revision=%s', scenario, revision)
                for command in control['commands']:
                    if scenario in ('command_timeout', 'offline'):
                        continue
                    cid, action = command['id'], command['action']
                    if cid not in completed:
                        if action == 'close_valve':
                            actuators['valve'] = 'closed'
                            message = '模拟阀门已关闭；此结果不是物理阀位反馈'
                        elif action == 'silence':
                            silenced_until = cycle + 15
                            message = '模拟蜂鸣器暂时消音 15 秒；报警与保护动作继续保留'
                        else:
                            message = '模拟采集、规则与控制路径自检通过；未验证真实硬件'
                        completed[cid] = message
                        # 先落本地执行记录再回执，控制通道重试时不会重复执行同一命令。
                        save_state(state_file, {'actuators': actuators, 'completed': completed})
                    client.post(base + f'/commands/{cid}/result', json={'success': True, 'message': completed[cid]}).raise_for_status()
            except (httpx.HTTPError, ValueError, KeyError):
                logging.warning('control channel unavailable; edge protection remains active')
            # offline 场景模拟遥测和控制通道中断 25 秒。
            sample = generate(scenario, cycle - start, sequence)
            state, active = evaluate(sample, rules, state, time.time())
            if 'gas' in active or 'fire' in active:
                actuators['valve'] = 'closed'
            actuators['fan'] = 'on' if 'gas' in active and 'fire' not in active else 'off'
            if 'fire' in active:
                actuators['power'] = 'off'
            actuators['buzzer'] = 'on' if active and cycle >= silenced_until else 'off'
            local_alarm = 'multiple' if len(active) > 1 else next(iter(active), 'normal')
            packet = {**sample, 'boot_id': boot, 'sequence': sequence,
                      'sampled_at': datetime.now(timezone.utc).isoformat(), 'local_alarm': local_alarm,
                      'actuators': actuators}
            # 即使后端停止，本地状态文件仍保留最后一份证据。
            save_state(state_file, {'actuators': actuators, 'completed': completed, 'sample': packet})
            if not (scenario == 'offline' and cycle - start < 25):
                try:
                    client.post(base + '/telemetry', json=packet).raise_for_status()
                except httpx.HTTPError:
                    logging.warning('telemetry upload failed; sample retained in local state')
            sequence += 1
            time.sleep(max(0.1, 1.0 - (time.monotonic() - cycle)))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # Ctrl+C 是正常的演示结束操作，不输出长 traceback。
        logging.info('edge simulator stopped')

"""文件职责：STM32 调试器实时采样网关。
主要功能：读取一致 RAM 快照、转换并上报状态，处理去重与重启，串行转交命令和阈值并回报结果。
技术栈：Python、pyOCD、CMSIS-DAP、SWD、HTTPX、Pydantic。
模块联动：复用 hardware_test 的唯一探针会话，FrameBuilder 转为 SampleInput，SwdCommands 提交固件信箱；固件保留自动保护优先权。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-09-30；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""
from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from backend.core.config import settings, PROJECT_ROOT
from backend.schemas import SampleInput
from gateway.swd_control import SwdCommands, ACTIONS
from gateway.wifi_config import apply_wifi

LOG = logging.getLogger('kitchen.swd')


class FrameBuilder:
    """为一次采集会话保存身份；MCU 序号或运行时间回退时重新生成身份。
    编写/修改日期（日志对应）：2026-09-30。
    """
    def __init__(self):
        """为本次 SWD 采集会话建立启动编号和上一快照记录，供去重与 MCU 重启识别。
        编写/修改日期（日志对应）：2026-09-30。
        """
        self.boot_id = 'swd-' + uuid4().hex
        self.previous: tuple[int, int] | None = None

    def build(self, state: dict) -> dict | None:
        """保留原始量和控制寄存器状态，跳过同一快照，生成严格接口数据。
        
        输入 hardware_test.read_status 的一致状态快照，返回设备 API 数据包；重复快照返回空，重启时更换启动身份。
        编写/修改日期（日志对应）：2026-09-30。
        """
        current = (state['sequence'], state['uptime_ms'])
        if self.previous == current:
            return None
        if self.previous and (current[0] < self.previous[0] or current[1] < self.previous[1]):
            self.boot_id = 'swd-' + uuid4().hex
        self.previous = current
        raw = {f'{name}_ao': state[f'{name}_raw'] for name in ('smoke', 'temp', 'gas', 'flame')}
        raw.update(smoke_do=state['smoke_do'], flame_do=state['flame_do'])
        # 日志对应：2026-09-22。新版使用固件的滤波与温度估算结果，保留原始通道用于比对。
        filtered = {f'{name}_ao': state.get(f'filtered_{name}_raw', state[f'{name}_raw'])
                    for name in ('smoke', 'temp', 'gas', 'flame')}
        # 日志对应：2026-09-26。隔离通道明确缺失，不让内部占位零值进入测量记录。
        smoke_enabled = bool(state.get('smoke_enabled', 1))
        if not smoke_enabled:
            raw.update(smoke_ao=None, smoke_do=None)
            filtered['smoke_ao'] = None
        temperature = state.get('temperature_centi_c', 0) / 100 if state.get('temperature_valid') else None
        flame = bool(state.get('flame_detected', filtered['flame_ao'] <= 1638 or state['flame_do']))
        # 日志对应：2026-09-24。旧固件只报告总报警，新固件直接报告危险位；均不混淆燃气与火灾。
        hazards = state.get('hazard_flags')
        if hazards is None:
            gas_alarm = (filtered['gas_ao'] * 100 + 2047) // 4095 >= 70
            fire_alarm = flame or (smoke_enabled and (filtered['smoke_ao'] * 100 + 2047) // 4095 >= 70)
            hazards = int(gas_alarm) | (int(fire_alarm) << 1)
        local_alarm = {0: 'normal', 1: 'gas', 2: 'fire', 3: 'multiple'}.get(hazards, 'sensor_fault')
        packet = {
            'boot_id': self.boot_id, 'sequence': current[0],
            'sampled_at': datetime.now(timezone.utc).isoformat(),
            'gas': state.get('effective_gas', (filtered['gas_ao'] * 100 + 2047) // 4095),
            'smoke': state.get('effective_smoke', (filtered['smoke_ao'] * 100 + 2047) // 4095) if smoke_enabled else None,
            'temperature': state.get('effective_temperature_centi', round(temperature * 100) if temperature is not None else -2147483648) / 100 if state.get('temperature_valid') else None,
            'valid': False,
            'monitoring_enabled': bool(state.get('monitoring_enabled', 1)),
            'test_scenario': {0: '', 1: 'gas', 2: 'smoke', 3: 'temperature', 4: 'flame', 5: 'multiple'}.get(state.get('test_scenario', 0), ''),
            'io_valid': state.get('adc_error_count', 0) == 0 and state.get('processing_test_failures', 0) == 0,
            # 日志对应：2026-09-24。火焰判断沿用固件结果，AO 低才增强；阈值仍未实物标定。
            'flame': bool(state.get('effective_flame', flame)),
            'local_alarm': local_alarm,
            # 日志对应：2026-09-24。寄存器只能证明控制输出，不能证明风机动作或物理阀位。
            'actuators': {
                'valve': 'closed' if state['servo_pulse_us'] == 500 else 'open',
                'fan': 'on' if state['gpio_a_output'] & (1 << 8) else 'off',
                'power': 'on' if state['gpio_b_output'] & (1 << 12) else 'off',
                'buzzer': 'on' if state['gpio_b_output'] & 1 else 'off',
            },
            'raw': raw, 'filtered': filtered, 'transport': 'swd',
            'disabled_sensors': [] if smoke_enabled else ['smoke'],
            'firmware': f"stm32f103-hwtest/{state['version']}.0" if state.get('version') else None,
            'control_capabilities': [name for name, code in ACTIONS.items()
                                     if state.get('control_capabilities', 0) & (1 << (code - 1))],
            'diagnostics': {name: state[name] for name in ('adc_error_count', 'processing_test_failures',
                'display_update_count', 'network_ready', 'command_sequence', 'command_result',
                'silence_remaining_ms', 'test_remaining_ms', 'gas_fan_demo_enabled', 'rules_revision',
                'gas_threshold', 'smoke_threshold', 'temperature_threshold_centi', 'sample_count', 'injection_remaining_ms', 'wifi_state', 'arming') if name in state},
        }
        if not packet['monitoring_enabled']:
            packet.update(gas=None, smoke=None, temperature=None, flame=False, raw=None, filtered=None, local_alarm='normal')
        return SampleInput.model_validate(packet).model_dump(mode='json', exclude_none=True)


def run(args) -> None:
    """持续读板、验证快照并上报；原始状态和 API 接收结果写入本地记录。
    编写/修改日期（日志对应）：2026-09-30。
    """
    # 探针依赖在运行采集时才加载，普通网页和协议测试无需安装硬件工具。
    from firmware.stm32f103_hardware_test.tools.hardware_test import open_session, read_status, status_address, symbol_address

    token = settings().hardware_device_token
    if not token:
        raise RuntimeError('Run python -m scripts.register_hardware first')
    endpoint = args.api_base_url.rstrip('/') + f'/api/v1/ingest/devices/{args.device_id}/telemetry'
    frames = FrameBuilder()
    startup_standby_sent = False
    log_path = PROJECT_ROOT / '.runtime' / 'hardware-test' / 'swd_ingest.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sent = 0
    with httpx.Client(timeout=5.0, trust_env=False) as http, open_session(
        args.uid, resume_on_disconnect=True
    ) as session, log_path.open('a', encoding='utf-8') as log:
        try:
            address = status_address()
            commands = None
            while args.samples == 0 or sent < args.samples:
                state = read_status(session.target, address)
                if state['fault_status'] or state['hardfault_status'] or state.get('processing_test_failures', 0):
                    raise RuntimeError('CPU fault flags detected; stopping hardware ingest')
                if state.get('version', 0) >= 5 and not startup_standby_sent:
                    # 系统启动先请求待机；真实险情存在时 MCU 会拒绝停止并保持保护。
                    control_address = symbol_address('g_hardware_control')
                    session.target.write32(control_address + 12, ACTIONS['stop_monitoring'])
                    session.target.write32(control_address + 8, int(time.time_ns() & 0xffffffff) or 1)
                    session.target.flush()
                    startup_standby_sent = True
                if state.get('version', 0) >= 5:
                    apply_wifi(session.target, symbol_address('g_wifi_config'))
                # 无线握手成功后，TCP 独占命令和遥测；SWD 保留配置及失联回退。
                wifi_lease = PROJECT_ROOT / '.runtime/wifi_link.json'
                wifi_live = False
                if wifi_lease.exists():
                    try:
                        wifi_live = time.time() - json.loads(wifi_lease.read_text())['at'] < 4
                    except (OSError, ValueError, KeyError):
                        pass
                if wifi_live:
                    time.sleep(args.interval)
                    continue
                if state.get('version', 0) >= 4:
                    if commands is None:
                        commands = SwdCommands(session.target, symbol_address('g_hardware_control'), http,
                            endpoint.rsplit('/telemetry', 1)[0], token)
                    try:
                        commands.step()
                    except httpx.HTTPError:
                        # 接口暂时失联时保留待回执命令；不重写信箱，也不中断本地独立保护。
                        LOG.warning('Command channel temporarily unavailable; keeping pending receipt')
                payload = frames.build(state)
                if payload:
                    # 日志对应：2026-10-01。丢失 HTTP 回应时重发同一包，后端可按身份与序号去重。
                    for attempt in range(3):
                        try:
                            response = http.post(endpoint, json=payload, headers={'Authorization': f'Bearer {token}'})
                            response.raise_for_status()
                            result = response.json()
                            if not result.get('accepted'):
                                raise RuntimeError('Backend did not accept the hardware sample')
                            break
                        except (httpx.TransportError, httpx.HTTPStatusError):
                            if attempt == 2:
                                raise
                            time.sleep(1)
                    log.write(json.dumps({'state': state, 'result': result}, ensure_ascii=False) + '\n')
                    log.flush()
                    sent += 1
                    LOG.info('hardware sample accepted: device=%s sequence=%s sample_id=%s',
                             args.device_id, payload['sequence'], result.get('sample_id'))
                time.sleep(args.interval)
        finally:
            # 日志对应：2026-09-26。正常退出 CPU 调试并关闭 HID，避开探针断开引起的重启。
            session.board.uninit()
            session.probe.close()


def main() -> None:
    """解析本地采集参数；退出时释放探针并让固件继续独立运行。
    编写/修改日期（日志对应）：2026-09-30。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device-id', default='stm32-001')
    parser.add_argument('--uid', default='ATK-20240820')
    parser.add_argument('--api-base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--samples', type=int, default=0, help='0 means run until stopped')
    parser.add_argument('--interval', type=float, default=0.5)
    args = parser.parse_args()
    if args.samples < 0 or args.interval <= 0:
        parser.error('samples must be >= 0 and interval must be > 0')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    # 日志对应：2026-09-26。Windows 总入口用 Ctrl+Break 退出子进程，也应执行探针清理。
    if hasattr(signal, 'SIGBREAK'):
        def stop_from_supervisor(signum, frame):
            """接到总入口退出信号时触发正常退出路径，让 finally 释放 HTTP 会话和探针。
            编写/修改日期（日志对应）：2026-09-30。
            """
            raise KeyboardInterrupt
        signal.signal(signal.SIGBREAK, stop_from_supervisor)
    try:
        run(args)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()

"""文件职责：已保存实机样本的复核工具。
主要功能：选择同次启动记录，复算连续八点均值，检查故障、显示刷新和 GPIO/PWM 策略。
技术栈：Python json、datetime、连续窗口计算。
模块联动：读取 gateway.swd 保存的样本，依据 sensor_processing 和 response_policy 规则对照；结果不代替执行器物理动作。
编写/修改日期（日志对应）：2026-09-25。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from backend.core.config import PROJECT_ROOT


def main() -> None:
    """选择新版实机样本，检查连续窗口；可按接线调整后的起点分别保存证据。
    编写/修改日期（日志对应）：2026-09-25。
    """
    root = PROJECT_ROOT / '.runtime' / 'hardware-test'
    # 日志对应：2026-09-25 自测。改线前后分别复核，不能把之前的满量程记录混作改线后结果。
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--since', type=datetime.fromisoformat)
    parser.add_argument('--output', type=type(root), default=root / 'sensor_processing_check.json')
    args = parser.parse_args()
    if args.since and args.since.tzinfo is None:
        parser.error('--since 必须包含时区')
    records = []
    for line in (root / 'swd_ingest.jsonl').read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        state = record['state']
        if state['version'] < 2:
            continue
        if args.since and datetime.fromisoformat(state['sampled_at']) < args.since:
            continue
        if records and (state['sequence'] < records[-1]['state']['sequence'] or
                        state['uptime_ms'] < records[-1]['state']['uptime_ms']):
            records.clear()
        if not records or state['sequence'] != records[-1]['state']['sequence']:
            records.append(record)
    if len(records) < 20:
        raise RuntimeError('至少需要同一次启动的 20 个真实样本，请保持采集后重试')
    frames = [record['state'] for record in records]
    windows = 0
    mismatches = []
    # 网关可能跳过帧；只对序号连续的窗口精确计算，不能把缺失帧拼成 8 点窗口。
    for index in range(7, len(frames)):
        window = frames[index - 7:index + 1]
        if not all(b['sequence'] == a['sequence'] + 1 for a, b in zip(window, window[1:])):
            continue
        windows += 1
        for channel in ('smoke', 'temp', 'gas', 'flame'):
            expected = (sum(item[channel + '_raw'] for item in window) + 4) // 8
            if frames[index]['filtered_' + channel + '_raw'] != expected:
                mismatches.append({'sequence': frames[index]['sequence'], 'channel': channel})
    temperatures = [item['temperature_centi_c'] / 100 for item in frames if item['temperature_valid']]
    # 日志对应：2026-09-25。核对实机寄存器输出与本地报警一致，物理动作仍需现场确认。
    output_mismatches = []
    for item in frames:
        alarm = bool(item['alarm'])
        # 日志对应：2026-09-24。新版按危险类型控制风扇，信号回落后仍保持阀门关闭。
        hazards = item.get('hazard_flags', 0)
        fan = bool(item.get('gas_fan_demo_enabled') and hazards & 1 and not hazards & 2)
        expected_fan = fan if item['version'] >= 3 else alarm
        valve_closed = bool(item.get('valve_latched', alarm))
        correct = (bool(item['gpio_a_output'] & (1 << 8)) == expected_fan and
                   bool(item['gpio_b_output'] & 1) == alarm and
                   bool(item['gpio_b_output'] & (1 << 12)) == alarm and
                   not item['gpio_b_output'] & (1 << 13) and
                   item['servo_pulse_us'] == (500 if valve_closed else 1500))
        if not correct:
            output_mismatches.append(item['sequence'])
    result = {
        'checked_at': datetime.now().astimezone().isoformat(),
        'samples': len(frames), 'sequence_start': frames[0]['sequence'], 'sequence_end': frames[-1]['sequence'],
        'consecutive_windows_checked': windows, 'filter_mismatches': mismatches,
        'temperature_estimate_range_c': [min(temperatures), max(temperatures)] if temperatures else None,
        'gas_adc_range': [min(item['gas_raw'] for item in frames), max(item['gas_raw'] for item in frames)],
        'oled_update_start': frames[0]['display_update_count'],
        'oled_update_end': frames[-1]['display_update_count'],
        'all_algorithm_tests_passed': all(item['processing_test_failures'] == 0 for item in frames),
        'all_adc_errors_zero': all(item['adc_error_count'] == 0 for item in frames),
        'all_cpu_faults_zero': all(item['fault_status'] == item['hardfault_status'] == 0 for item in frames),
        'all_samples_accepted': all(item['result']['accepted'] for item in records),
        'alarm_frames': sum(bool(item['alarm']) for item in frames),
        'idle_frames': sum(not item['alarm'] for item in frames),
        'alarm_state_changes': sum(a['alarm'] != b['alarm'] for a, b in zip(frames, frames[1:])),
        'output_register_mismatches': output_mismatches,
        # 日志对应：2026-09-26。端点计数只提示量程检查，不把饱和误当作已标定浓度。
        'adc_ranges': {channel: [min(item[channel + '_raw'] for item in frames),
                                  max(item[channel + '_raw'] for item in frames)]
                       for channel in ('smoke', 'temp', 'gas', 'flame')},
        'high_rail_samples': {channel: sum(item[channel + '_raw'] == 4095 for item in frames)
                              for channel in ('smoke', 'temp', 'gas', 'flame')},
    }
    result['passed'] = bool(windows and not mismatches and not output_mismatches and result['all_algorithm_tests_passed'] and
                            result['all_adc_errors_zero'] and result['all_cpu_faults_zero'] and
                            result['all_samples_accepted'] and
                            result['oled_update_end'] > result['oled_update_start'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['passed']:
        raise RuntimeError('实机采样复核未通过，请检查 sensor_processing_check.json')


if __name__ == '__main__':
    main()

"""文件职责：报警条件和恢复状态机。
主要功能：依据阈值、持续时间、回差与恢复时间判断燃气、火灾和采样异常。
技术栈：Python 纯函数、状态机、时间判定。
模块联动：模拟器和 monitoring.ingest 调用 evaluate；实物测试通道与是否标定分别判断，相对指标不是浓度标定结果。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-09-24；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""
DEFAULT_RULES = {'gas_threshold': 40.0, 'smoke_threshold': 45.0, 'temperature_threshold': 60.0,
                 'hold_seconds': 3.0, 'recovery_seconds': 5.0, 'hysteresis': 5.0,
                 'offline_seconds': 12, 'command_timeout_seconds': 15,
                 'gas_manual_threshold': 80.0, 'auto_response_timeout_seconds': 30}


def evaluate(sample: dict, rules: dict, previous: dict, now: float):
    """根据当前采样和上一状态计算报警集合。

    ``since`` 与 ``clear_since`` 用于实现持续时间和恢复时间，避免
    一次瞬时尖峰直接触发报警，也避免数值刚回落就立即关闭报警。

    输入为当前采样、规则、上一轮状态和秒级时间；返回新的状态字典与活动报警集合，不访问数据库。
    编写/修改日期（日志对应）：2026-09-24。
    """
    # 这里故意不读数据库，也不调用网络：同一份规则既能在边缘模拟器运行，
    # 也能在服务端复核上报结果，后续换成真实单片机时有清楚的行为基准。
    state = {k: dict(v) for k, v in previous.items()}
    valid = sample.get('valid', False) and all(sample.get(k) is not None for k in ('gas', 'smoke', 'temperature'))
    # 日志对应：2026-09-26。硬件联调中的完整原始通道可复核测试信号；valid=false 仍保留待标定告警。
    raw = sample.get('raw') or {}
    test_channels = (sample.get('io_valid') is True and sample.get('transport') in ('swd', 'tcp', 'uart') and not sample.get('disabled_sensors') and
                     all(raw.get(k + '_ao') is not None for k in ('gas', 'smoke', 'temp', 'flame')) and
                     all(sample.get(k) is not None for k in ('gas', 'smoke', 'temperature')))
    usable = valid or test_channels
    reported = sample.get('local_alarm', '')
    # 日志对应：2026-10-15。待机不是正常采样，也不制造传感器故障；旧异常按恢复窗口结束且仍待确认。
    standby = sample.get('monitoring_enabled') is False
    active = set()
    for kind in ('gas', 'fire', 'sensor_fault'):
        item = state.setdefault(kind, {'active': False, 'since': None, 'clear_since': None})
        h = rules['hysteresis'] if item['active'] else 0
        if kind == 'gas':
            condition = reported in ('gas', 'multiple') or (usable and sample['gas'] >= rules['gas_threshold'] - h)
        elif kind == 'fire':
            # 火焰/本地火灾信号不能因其他通道待标定被屏蔽，直接进入火灾警情。
            condition = (sample.get('flame', False) or reported in ('fire', 'multiple') or
                         (usable and (sample['smoke'] >= rules['smoke_threshold'] - h or
                                      sample['temperature'] >= rules['temperature_threshold'] - h)))
        else:
            condition = not usable
        # 无效采样不能替危险报警“洗白”，必须等待有效数据恢复并保持人工可见。
        if not usable and kind != 'sensor_fault' and item['active']:
            condition = True
        if standby:
            condition = False
        if condition:
            item['clear_since'] = None
            if item['since'] is None:
                item['since'] = now
            # 日志对应：2026-10-13。本地已经触发的保护报警直接入事件，避免边缘与平台重复等待。
            local_trip = (kind == 'gas' and reported in ('gas', 'multiple')) or (
                kind == 'fire' and (sample.get('flame') or reported in ('fire', 'multiple')))
            hold = 0 if kind == 'sensor_fault' or local_trip else rules['hold_seconds']
            if now - item['since'] >= hold:
                item['active'] = True
        else:
            item['since'] = None
            if item['clear_since'] is None:
                item['clear_since'] = now
            if now - item['clear_since'] >= rules['recovery_seconds']:
                item['active'] = False
        if item['active']:
            active.add(kind)
    return state, active

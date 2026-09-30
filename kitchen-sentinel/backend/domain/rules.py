"""供模拟器和服务端复核共同使用的纯规则函数。

燃气和烟雾是 0 到 100 的相对演示指标，不是经过标定的 ppm 或 %LEL；
所有持续时间都使用秒，报警恢复也不会自动重新打开已经关闭的燃气阀门。
"""
DEFAULT_RULES = {'gas_threshold': 40.0, 'smoke_threshold': 45.0, 'temperature_threshold': 60.0,
                 'hold_seconds': 3.0, 'recovery_seconds': 5.0, 'hysteresis': 5.0,
                 'offline_seconds': 12, 'command_timeout_seconds': 15}


def evaluate(sample: dict, rules: dict, previous: dict, now: float):
    """根据当前采样和上一状态计算报警集合。

    ``since`` 与 ``clear_since`` 用于实现持续时间和恢复时间，避免
    一次瞬时尖峰直接触发报警，也避免数值刚回落就立即关闭报警。
    """
    # 这里故意不读数据库，也不调用网络：同一份规则既能在边缘模拟器运行，
    # 也能在服务端复核上报结果，后续换成真实单片机时有清楚的行为基准。
    state = {k: dict(v) for k, v in previous.items()}
    valid = sample.get('valid', False) and all(sample.get(k) is not None for k in ('gas', 'smoke', 'temperature'))
    active = set()
    for kind in ('gas', 'fire', 'sensor_fault'):
        item = state.setdefault(kind, {'active': False, 'since': None, 'clear_since': None})
        h = rules['hysteresis'] if item['active'] else 0
        if kind == 'gas':
            condition = valid and sample['gas'] >= rules['gas_threshold'] - h
        elif kind == 'fire':
            condition = valid and (sample.get('flame', False) or sample['smoke'] >= rules['smoke_threshold'] - h
                                   or sample['temperature'] >= rules['temperature_threshold'] - h)
        else:
            condition = not valid
        # 无效采样不能替危险报警“洗白”，必须等待有效数据恢复并保持人工可见。
        if not valid and kind != 'sensor_fault' and item['active']:
            condition = True
        if condition:
            item['clear_since'] = None
            if item['since'] is None:
                item['since'] = now
            hold = 0 if kind == 'sensor_fault' or (kind == 'fire' and sample.get('flame')) else rules['hold_seconds']
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

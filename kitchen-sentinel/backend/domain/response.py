"""文件职责：自动响应与人工处置判定。
主要功能：分别计算自动动作反馈、恢复状态、超限或超时升级、历史记录兼容显示。
技术栈：Python 纯函数、状态字典、阈值和超时判断。
模块联动：monitoring 根据最新采样和输出反馈调用本文件，platform 保存人员处置；寄存器不代替阀位与灭火效果。
编写/修改日期（日志对应）：2026-10-05；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""

REASON_LABELS = {'fire': '火灾警情超出自动处置能力', 'beyond_limit': '超过自动处置范围',
                 'automatic_timeout': '自动响应后信号持续，超过观察时限',
                 'reconnect_timeout': '自动重连观察超时，需检查现场连接',
                 'execution_failed': '保护命令执行失败',
                 'inspection_required': '采样或连接异常需要核查', 'historical_review': '历史事件需要复核',
                 'onsite_issue': '现场观察到自动执行异常，需人工核查'}


def evaluate_response(kind, active, elapsed, sample, actuators, config, previous=None, source='hardware', failed=False):
    """返回处置进度；升级人工的原因保留到人工完成核查，普通恢复不清除报警确认。
    
    输入危险类型、持续时长、采样、输出报告和上轮处置；返回动作比对、自动进度及人工升级原因，不下发执行器命令。
    编写/修改日期（日志对应）：2026-10-05。
    """
    previous = previous or {}
    reasons = list(previous.get('reasons', []))
    if failed and 'execution_failed' not in reasons:
        reasons.append('execution_failed')
    targets = {'valve': 'closed', 'buzzer': 'on'} if active else {'valve': 'closed'}
    if kind == 'fire':
        targets['fan'] = 'off'
        if active:
            # 硬件字段表示继电器保护输出有效，模拟器字段表示被保护电源关闭。
            targets['power'] = 'off' if source == 'simulated' else 'on'
        if 'fire' not in reasons:
            reasons.append('fire')
    elif kind == 'gas':
        if active:
            # 火灾优先级更高，复合危险必须停普通风扇；低压模型支持燃气排风联动。
            fire = sample.get('local_alarm') in ('fire', 'multiple') or sample.get('flame')
            fan_enabled = sample.get('diagnostics', {}).get('gas_fan_demo_enabled', source == 'simulated')
            if fire or fan_enabled:
                targets['fan'] = 'off' if fire else 'on'
            if not fire and sample.get('diagnostics', {}).get('silence_remaining_ms', 0) > 0:
                targets['buzzer'] = 'off'
        value = sample.get('gas')
        if active and value is not None and value >= config['gas_manual_threshold'] and 'beyond_limit' not in reasons:
            reasons.append('beyond_limit')
        if active and elapsed >= config['auto_response_timeout_seconds'] and 'automatic_timeout' not in reasons:
            reasons.append('automatic_timeout')
    elif kind == 'offline':
        targets = {}
        if active and elapsed >= config['auto_response_timeout_seconds'] and 'reconnect_timeout' not in reasons:
            reasons.append('reconnect_timeout')
    else:
        targets = {}
        if 'inspection_required' not in reasons:
            reasons.append('inspection_required')
    actions = [{'actuator': key, 'expected': value, 'reported': actuators.get(key),
                'matched': actuators.get(key) == value} for key, value in targets.items()]
    reported = bool(actions) and all(item['matched'] for item in actions)
    if kind == 'offline':
        status = 'reconnecting' if active else 'connection_recovered'
    elif kind in ('sensor_fault', 'control_fault'):
        status = 'inspection_required'
    elif not active:
        # 模拟器可验证软件闭环；实物控制引脚反馈仍只能说明测试信号恢复，不能替代现场核验。
        status = ('auto_resolved' if kind == 'gas' and not reasons and source == 'simulated' and
                  sample.get('valid') and reported else 'signal_recovered')
    elif reported:
        status = 'protection_reported' if kind == 'fire' else 'monitoring'
    else:
        status = 'awaiting_feedback'
    resolution = previous.get('resolution')
    return {'automatic_status': status, 'manual_required': bool(reasons) and not resolution,
            'reasons': reasons, 'actions': actions, 'resolution': resolution,
            'feedback_level': 'simulated_feedback' if source == 'simulated' else 'control_outputs',
            'automatic_timeout_seconds': config['auto_response_timeout_seconds'],
            'gas_manual_threshold': config['gas_manual_threshold']}


def response_view(alarm):
    """兼容历史事件；未保存自动回执的旧记录明确标记，不能补造执行结果。
    编写/修改日期（日志对应）：2026-10-05。
    """
    saved = (alarm.evidence or {}).get('response')
    if saved:
        return saved
    manual = alarm.kind in ('fire', 'sensor_fault', 'control_fault') or (alarm.kind == 'offline' and alarm.status == 'active')
    return {'automatic_status': 'not_recorded', 'manual_required': manual,
            'reasons': ['historical_review'] if manual else [], 'actions': [],
            'resolution': None, 'feedback_level': 'not_recorded'}

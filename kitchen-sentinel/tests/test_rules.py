"""文件职责：报警阈值与恢复状态机测试。
主要功能：验证短时尖峰抑制、持续越限触发、恢复等待与无效数据保护。
技术栈：pytest、Python 纯函数、状态字典。
模块联动：直接调用 domain.rules.evaluate，不访问数据库或设备。
编写/修改日期（日志对应）：2026-09-25。
"""

from backend.domain.rules import DEFAULT_RULES, evaluate


def sample(**overrides):
    """构造正常采样基线并按关键字覆盖指定字段，供规则边界用例保持相同初始条件。
    编写/修改日期（日志对应）：2026-09-25。
    """
    value = {'gas': 8, 'smoke': 8, 'temperature': 25, 'flame': False, 'valid': True}
    value.update(overrides)
    return value


def test_short_gas_spike_does_not_alarm():
    """模拟短时越限后回落，验证持续时间未满足时不进入燃气报警状态。
    编写/修改日期（日志对应）：2026-09-25。
    """
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, {}, 0)
    assert 'gas' not in active
    state, active = evaluate(sample(gas=8), DEFAULT_RULES, state, 2)
    assert 'gas' not in active


def test_sustained_gas_alarm_latches_until_recovery():
    """模拟持续越限与回落，验证报警触发后须满足恢复等待时间才解除条件。
    编写/修改日期（日志对应）：2026-09-25。
    """
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, {}, 0)
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, state, 3)
    assert 'gas' in active
    state, active = evaluate(sample(gas=8), DEFAULT_RULES, state, 4)
    assert 'gas' in active
    state, active = evaluate(sample(gas=8), DEFAULT_RULES, state, 9)
    assert 'gas' not in active


def test_invalid_data_does_not_clear_hazard():
    """验证无效采样不会把已存在危险清除，并会追加采样异常状态。
    编写/修改日期（日志对应）：2026-09-25。
    """
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, {}, 0)
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, state, 3)
    state, active = evaluate(sample(valid=False, gas=None), DEFAULT_RULES, state, 4)
    assert 'gas' in active
    assert 'sensor_fault' in active

from backend.domain.rules import DEFAULT_RULES, evaluate


def sample(**overrides):
    value = {'gas': 8, 'smoke': 8, 'temperature': 25, 'flame': False, 'valid': True}
    value.update(overrides)
    return value


def test_short_gas_spike_does_not_alarm():
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, {}, 0)
    assert 'gas' not in active
    state, active = evaluate(sample(gas=8), DEFAULT_RULES, state, 2)
    assert 'gas' not in active


def test_sustained_gas_alarm_latches_until_recovery():
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, {}, 0)
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, state, 3)
    assert 'gas' in active
    state, active = evaluate(sample(gas=8), DEFAULT_RULES, state, 4)
    assert 'gas' in active
    state, active = evaluate(sample(gas=8), DEFAULT_RULES, state, 9)
    assert 'gas' not in active


def test_invalid_data_does_not_clear_hazard():
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, {}, 0)
    state, active = evaluate(sample(gas=70), DEFAULT_RULES, state, 3)
    state, active = evaluate(sample(valid=False, gas=None), DEFAULT_RULES, state, 4)
    assert 'gas' in active
    assert 'sensor_fault' in active

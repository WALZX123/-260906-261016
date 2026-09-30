"""使用真实套接字验证端口选择，避免只测试模拟的占用状态。"""

import socket

import pytest

from scripts.ports import select_port


def test_available_port_keeps_preferred():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        preferred = probe.getsockname()[1]
    port, reason = select_port('127.0.0.1', preferred)
    assert port == preferred
    assert reason is None


def test_occupied_port_selects_another():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen(1)
        preferred = occupied.getsockname()[1]
        if preferred > 65515:
            pytest.skip('随机分配的端口接近上限，无法顺序探测')
        port, reason = select_port('127.0.0.1', preferred)
        assert preferred < port < preferred + 20
        assert reason is not None


def test_no_available_port_returns_readable_error():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen(1)
        with pytest.raises(RuntimeError, match='均不可用'):
            select_port('127.0.0.1', occupied.getsockname()[1], attempts=1)

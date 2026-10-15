"""文件职责：监听端口选择测试。
主要功能：验证可用端口保留、占用时切换和候选范围耗尽时的可读错误。
技术栈：pytest、Python socket。
模块联动：使用本机真实套接字调用 scripts.ports，避免只靠模拟的端口占用判断。
编写/修改日期（日志对应）：2026-09-26。
"""

import socket

import pytest

from scripts.ports import select_port


def test_available_port_keeps_preferred():
    """绑定可用本机端口，验证选择器保留首选值而不无故换端口。
    编写/修改日期（日志对应）：2026-09-26。
    """
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        preferred = probe.getsockname()[1]
    port, reason = select_port('127.0.0.1', preferred)
    assert port == preferred
    assert reason is None


def test_occupied_port_selects_another():
    """用真实套接字占用首选端口，验证程序选择后续可用端口且保留原服务。
    编写/修改日期（日志对应）：2026-09-26。
    """
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
    """占满限定候选范围，验证程序报告可读的端口选择错误。
    编写/修改日期（日志对应）：2026-09-26。
    """
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen(1)
        with pytest.raises(RuntimeError, match='均不可用'):
            select_port('127.0.0.1', occupied.getsockname()[1], attempts=1)

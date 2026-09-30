"""本地入口共用的运行时辅助函数。

项目启动脚本始终使用 ``.venv`` 中的 Python，即使用户从 IDE 或系统
Python 启动，也不会出现“一个终端能运行、另一个终端缺少依赖”的问题。
"""

from __future__ import annotations

import os
import contextlib
import signal
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def ensure_project_python() -> None:
    """使用项目虚拟环境重新执行当前入口，并保留参数和退出码。"""

    if not PROJECT_PYTHON.exists():
        raise SystemExit(
            f"未找到项目虚拟环境解释器：{PROJECT_PYTHON}\n"
            "请先在项目目录创建 .venv 并安装 requirements.txt。"
        )

    current = Path(sys.executable).resolve()
    expected = PROJECT_PYTHON.resolve()
    if current == expected:
        return

    entry_point = Path(sys.argv[0]).resolve()
    command = [str(expected), str(entry_point), *sys.argv[1:]]
    if os.name == "nt":
        # Windows 的虚拟环境启动器可能把 ``os.execv`` 的第一个参数误当成脚本路径。
        # 这里改用独立进程组：父进程负责转发 Ctrl+C，并把子进程的退出码传回给调用方。
        # 直接使用 ``subprocess.run`` 时，Python 3.14 在等待子进程期间会把 Ctrl+C
        # 抛在 ``communicate`` 内部，最终留下误导性的 KeyboardInterrupt 回溯。
        process = subprocess.Popen(
            command,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            return_code = process.wait()
        except KeyboardInterrupt:
            # 先发送控制台中断，让 Uvicorn 和模拟器有机会执行正常的 shutdown 钩子。
            with contextlib.suppress(OSError, ValueError):
                process.send_signal(signal.CTRL_BREAK_EVENT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 只有子进程没有在宽限期内退出时才强制结束，避免孤儿进程继续占用端口。
                with contextlib.suppress(OSError):
                    process.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=5)
            raise SystemExit(0)
        raise SystemExit(return_code)
    os.execv(str(expected), command)

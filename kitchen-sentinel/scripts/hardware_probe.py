"""文件职责：调试器和芯片身份检查入口。
主要功能：检查设备包和 pyOCD，读取目标身份、容量与启动向量并报告环境错误。
技术栈：Python subprocess、pyOCD commander、CMSIS-DAP。
模块联动：使用项目虚拟环境和 STM32 官方设备包；仅作为诊断入口，完整下载与稳定快照由 hardware_test 实现。
编写/修改日期（日志对应）：2026-09-25。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / '.runtime' / 'hardware-test' / 'Keil.STM32F1xx_DFP.2.3.0.pack'


def main() -> int:
    """检查 pyOCD 和官方设备包，按指定探针执行只读身份检查，将子进程退出码返回调用方。
    编写/修改日期（日志对应）：2026-09-25。
    """
    parser = argparse.ArgumentParser(description='只读检查 STM32F103C8 的 CMSIS-DAP 环境')
    parser.add_argument('--uid', default='ATK-20240820')
    args = parser.parse_args()
    pyocd = shutil.which('pyocd') or str(ROOT / '.venv' / 'Scripts' / 'pyocd.exe')
    if not Path(pyocd).exists():
        print('未找到 pyocd，请先安装 requirements-hardware.txt', file=sys.stderr)
        return 2
    if not PACK.is_file():
        print(f'缺少官方设备包：{PACK}', file=sys.stderr)
        return 2
    command = [pyocd, 'commander', '--pack', str(PACK), '-t', 'STM32F103C8', '-u', args.uid,
               '-M', 'attach', '-c', 'read32 0xE0042000 4', '-c', 'read32 0x1FFFF7E0 4',
               '-c', 'read32 0x08000000 16', '-c', 'exit']
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    print(completed.stdout, end='')
    if completed.stderr:
        print(completed.stderr, end='', file=sys.stderr)
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())

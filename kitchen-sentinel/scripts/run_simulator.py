"""设备模拟器单独启动入口。

脚本只负责路径和解释器准备，具体采样与协议行为位于 ``simulator.main``。
"""
import sys

try:
    from scripts.runtime import PROJECT_ROOT, ensure_project_python
except ModuleNotFoundError:  # 通过绝对文件路径直接执行时使用脚本目录导入。
    from runtime import PROJECT_ROOT, ensure_project_python

ensure_project_python()
sys.path.insert(0, str(PROJECT_ROOT))

from simulator.main import main  # noqa: E402


if __name__ == '__main__':
    main()

"""文件职责：模拟器单独运行入口。
主要功能：确定项目目录和虚拟环境，再进入设备模拟器。
技术栈：Python、项目虚拟环境、模块导入和函数调用。
模块联动：复用 scripts.runtime，执行 simulator.main；模拟数据不写为实物数据。
编写/修改日期（日志对应）：2026-09-25。
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

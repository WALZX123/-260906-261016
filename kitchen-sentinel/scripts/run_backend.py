"""文件职责：后端单独运行入口。
主要功能：确定项目目录、切换虚拟环境，再启动 Uvicorn 服务。
技术栈：Python、项目虚拟环境、Uvicorn。
模块联动：复用 scripts.runtime 的解释器检查，加载 backend.main；整套启动与回收由 start.py 负责。
编写/修改日期（日志对应）：2026-09-11。
"""

import sys

try:
    from scripts.runtime import PROJECT_ROOT, ensure_project_python
except ModuleNotFoundError:  # 通过绝对文件路径直接执行时使用脚本目录导入。
    from runtime import PROJECT_ROOT, ensure_project_python

ensure_project_python()
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn  # noqa: E402


if __name__ == '__main__':
    uvicorn.run('backend.main:app', host='127.0.0.1', port=8000, reload=False)

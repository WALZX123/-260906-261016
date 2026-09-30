"""后端单独启动入口。

脚本不依赖当前终端目录，并在导入 Uvicorn 前确保使用项目虚拟环境。
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

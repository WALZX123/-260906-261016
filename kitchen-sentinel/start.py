"""灶安系统总入口：准备数据库，托管 API、网页和设备模拟器。

前端为 React + TypeScript，构建后的 dist 由 FastAPI 提供；数据库使用
SQLAlchemy + MySQL。入口检查资源、端口和健康状态，并统一回收进程。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from scripts.processes import ProcessSupervisor
from scripts.ports import select_port
from scripts.runtime import PROJECT_ROOT, ensure_project_python


# 前端退出按钮通过这个短生命周期标记通知总入口：后端收到请求后先优雅停机，
# 总入口再回收模拟器和其他子进程。标记只存在于本次运行期间，不参与业务数据。
SHUTDOWN_MARKER = PROJECT_ROOT / '.runtime' / 'shutdown.request'


def port_number(value: str) -> int:
    """提前拒绝非法端口，避免在驱动或网络层出现难懂的错误。"""
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('端口必须是整数') from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError('端口范围必须为 1–65535')
    return port


def parse_args() -> argparse.Namespace:
    """本地演示默认监听 127.0.0.1；其他模式由参数显式选择。"""
    parser = argparse.ArgumentParser(description='启动灶安本地全栈演示系统')
    parser.add_argument('--host', default='127.0.0.1', help='监听 IPv4 地址或主机名')
    parser.add_argument('--port', type=port_number, default=8000, help='API 和网页端口，默认 8000')
    parser.add_argument('--skip-bootstrap', action='store_true', help='跳过已完成的数据库初始化')
    parser.add_argument('--no-simulator', action='store_true', help='只启动网页和 API')
    parser.add_argument('--no-browser', action='store_true', help='启动后不自动打开浏览器')
    return parser.parse_args()


def check_resources() -> None:
    """启动前检查项目文件，端口选择由 ports 模块单独负责。"""
    if not (PROJECT_ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        raise RuntimeError('前端构建不存在，请先在 frontend 目录执行构建')
    if not (PROJECT_ROOT / '.env').is_file():
        raise RuntimeError('缺少 .env，请复制 .env.example 并填写数据库账号密码')


def wait_for_backend(url: str, process: subprocess.Popen, timeout: float = 30.0) -> None:
    """数据库可查询且后端完成启动后，才启动模拟器和打开浏览器。"""
    deadline = time.monotonic() + timeout
    # 本机健康检查不走用户代理，避免代理把 localhost 请求转发出去。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'后端提前退出（退出码 {process.returncode}），请查看上方服务日志')
        try:
            with opener.open(url + '/api/health', timeout=1) as response:
                data = json.loads(response.read())
            if isinstance(data, dict) and data.get('status') == 'ok' and process.poll() is None:
                return
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            pass
        time.sleep(0.5)
    raise TimeoutError(f'后端在 {timeout:.0f} 秒内未就绪，请检查数据库连接')


def main() -> int:
    """总入口；所有退出分支都经过 finally 释放本次启动的进程。"""
    ensure_project_python()
    args = parse_args()
    local_host = '127.0.0.1' if args.host == '0.0.0.0' else args.host
    supervisor = None
    try:
        # 避免上一次异常退出留下的通知影响本次启动判断。
        SHUTDOWN_MARKER.unlink(missing_ok=True)
        check_resources()
        preferred_port = args.port
        args.port, reason = select_port(args.host, preferred_port)
        if args.port != preferred_port:
            print(f'{args.host}:{preferred_port} 暂不可用：{reason}；自动使用端口 {args.port}。', flush=True)
        # 只在端口最终确定后生成访问地址，保证浏览器、模拟器与来源白名单一致。
        base_url = f'http://{local_host}:{args.port}'
        supervisor = ProcessSupervisor()
        if not args.skip_bootstrap:
            print('[1/3] 检查数据库、执行迁移并准备演示数据…', flush=True)
            bootstrap = supervisor.spawn(
                [sys.executable, str(PROJECT_ROOT / 'scripts' / 'bootstrap.py')], PROJECT_ROOT,
            )
            try:
                result = bootstrap.wait(timeout=60)
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError('数据库初始化超时，请检查 MySQL 服务') from exc
            if result != 0:
                raise RuntimeError(f'数据库初始化失败（退出码 {result}），请检查 MySQL 服务及 .env 配置')

        # 切换端口也要添加对应浏览器来源，否则登录与 WebSocket 会被白名单拒绝。
        child_env = os.environ.copy()
        from backend.core.config import settings
        origins = {item.strip() for item in settings().allowed_origins.split(',') if item.strip()}
        origins.add(base_url)
        if local_host in ('127.0.0.1', 'localhost'):
            origins.update({f'http://127.0.0.1:{args.port}', f'http://localhost:{args.port}'})
        child_env['ALLOWED_ORIGINS'] = ','.join(sorted(origins))
        print('[2/3] 启动后端 API 和浏览器端…', flush=True)
        backend = supervisor.spawn(
            [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', args.host, '--port', str(args.port)],
            PROJECT_ROOT, child_env,
        )
        wait_for_backend(base_url, backend)
        simulator = None
        if not args.no_simulator:
            print('[3/3] 启动设备模拟器…', flush=True)
            simulator = supervisor.spawn(
                [sys.executable, '-m', 'simulator.main', '--url', base_url], PROJECT_ROOT, child_env,
            )
        print(f'系统已启动：{base_url}\n账号信息：.runtime/access.txt\n按 Ctrl+C 停止整个系统。', flush=True)
        if not args.no_browser:
            try:
                if not webbrowser.open(base_url):
                    print('浏览器未自动打开，请手动访问上述地址。', flush=True)
            except webbrowser.Error:
                print('浏览器未自动打开，请手动访问上述地址。', flush=True)
        while True:
            for name, process in (('后端', backend), ('模拟器', simulator)):
                if process is not None and process.poll() is not None:
                    # 只有本机前端发出的退出请求才走正常成功分支；其他异常退出仍然需要提示。
                    if name == '后端' and SHUTDOWN_MARKER.exists():
                        return 0
                    raise RuntimeError(f'{name}已退出（退出码 {process.returncode}），正在停止其余进程')
            time.sleep(0.5)
    except KeyboardInterrupt:
        print('\n正在停止系统…', flush=True)
        return 0
    except (RuntimeError, OSError, ValueError, ImportError) as exc:
        print(f'启动或运行失败：{exc}', file=sys.stderr, flush=True)
        return 1
    finally:
        if supervisor:
            supervisor.close()
        SHUTDOWN_MARKER.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())

"""文件职责：后端应用入口和实时服务。
主要功能：挂载 REST 路由和 React 页面，运行周期维护，提供健康检查、WebSocket 与本机退出接口。
技术栈：FastAPI、asyncio、SQLAlchemy、WebSocket、StaticFiles。
模块联动：start.py 启动本应用；API 和 monitoring 处理业务；useMonitor 订阅快照；退出标记交给总入口回收进程。
编写/修改日期（日志对应）：2026-10-15（设备启用和双向联调修正）；2026-10-03；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""

import asyncio
import contextlib
import json
import logging
import secrets
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 允许直接执行 `python backend/main.py`，同时兼容从项目根目录导入 backend.main。
PROJECT_ROOT_FOR_SCRIPT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT_FOR_SCRIPT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FOR_SCRIPT))

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from backend.core.config import settings, PROJECT_ROOT  # noqa: E402
from backend.core.db import SessionLocal  # noqa: E402
from backend.core.security import digest  # noqa: E402
from backend.models import AuthSession, User, utcnow  # noqa: E402
from backend.api import auth, devices, platform, testing  # noqa: E402
from backend.services.monitoring import maintenance, snapshot  # noqa: E402
from backend.services.live import updates  # noqa: E402
from backend.api import wifi  # noqa: E402
from scripts.instance import APP_VERSION, PROJECT_ID  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
log = logging.getLogger('kitchen')
SHUTDOWN_MARKER = PROJECT_ROOT / '.runtime' / 'shutdown.request'


def run_maintenance():
    """在线程池中执行一次数据库维护，避免阻塞事件循环。
    编写/修改日期（日志对应）：2026-10-03。
    """
    with SessionLocal.begin() as db:
        maintenance(db)


async def maintenance_loop():
    """周期维护离线设备和超时命令；单次异常不能杀死整个后台任务。
    编写/修改日期（日志对应）：2026-10-03。
    """
    while True:
        try:
            await asyncio.to_thread(run_maintenance)
        except SQLAlchemyError:
            log.exception('maintenance database operation failed')
        except Exception:
            # 规则数据损坏、第三方驱动异常等非数据库错误也要记录并继续下一轮。
            log.exception('maintenance task failed unexpectedly')
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app):
    """应用启动时验证数据库，关闭时等待维护任务完成取消。

    启动时验证数据库并创建维护任务；关闭时取消并等待任务，避免维护协程遗留。
    编写/修改日期（日志对应）：2026-10-03。
    """
    with SessionLocal() as db:
        db.execute(text('SELECT 1'))
    task = asyncio.create_task(maintenance_loop())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await asyncio.to_thread(testing.stop_owned)


app = FastAPI(title='Kitchen Sentinel 厨房安全监测平台', version=APP_VERSION, lifespan=lifespan,
              description='本机全栈原型；STM32 实物测试与独立模拟节点；设备协议 kitchen.v1')
# 配置允许写成逗号分隔字符串；去掉空白和空项，避免浏览器来源比较失败。
ALLOWED_ORIGINS = [item.strip() for item in settings().allowed_origins.split(',') if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_credentials=True, allow_methods=['GET', 'POST', 'PUT'],
                   allow_headers=['Content-Type', 'X-CSRF-Token', 'Authorization', 'X-Local-Exit'])


@app.middleware('http')
async def tracing(request: Request, call_next):
    # 每个请求都带追踪编号，现场演示出现异常时可以从日志和页面响应对应起来。
    """为每次 HTTP 请求记录耗时和追踪标识，调用下一层处理后返回原响应，异常继续交给全局处理。
    编写/修改日期（日志对应）：2026-10-03。
    """
    request_id = secrets.token_hex(8)
    try:
        response = await call_next(request)
    except SQLAlchemyError:
        log.error('database_error request_id=%s path=%s', request_id, request.url.path)
        return JSONResponse({'detail': '数据库操作失败，请查看服务状态', 'request_id': request_id}, status_code=503)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path.startswith('/api') or request.url.path in ('/', '/index.html'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    """统一兜底未处理异常，给浏览器可读响应并保留完整服务端日志。
    编写/修改日期（日志对应）：2026-10-03。
    """

    request_id = secrets.token_hex(8)
    log.exception('unhandled_error request_id=%s path=%s', request_id, request.url.path)
    return JSONResponse(
        {'detail': '服务器内部错误，请查看服务日志', 'request_id': request_id},
        status_code=500,
    )


app.include_router(wifi.router, prefix='/api/v1')
app.include_router(auth.router, prefix='/api/v1')
app.include_router(platform.router, prefix='/api/v1')
app.include_router(devices.router, prefix='/api/v1')
app.include_router(testing.router, prefix='/api/v1')


@app.get('/api/health')
def health():
    """健康检查只验证数据库连接，不依赖登录状态。
    编写/修改日期（日志对应）：2026-10-03。
    """
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
        return {'status': 'ok', 'version': APP_VERSION, 'application': 'kitchen-sentinel', 'project_id': PROJECT_ID, 'capabilities': ['alarm_escalation', 'hardware_commands', 'activation', 'wifi']}
    except SQLAlchemyError:
        return JSONResponse({'status': 'degraded'}, status_code=503)


@app.post('/api/shutdown', status_code=202)
async def shutdown(request: Request):
    """响应本机前端的退出请求，安全停止当前整套演示进程。

    这个接口刻意不要求登录，便于用户在登录页或会话失效后退出系统；但它只接受
    回环地址和前端专用请求头，不能被局域网中的其他设备远程调用。先写入临时标记，
    再延迟发送 SIGINT，让 202 响应有机会返回浏览器，应用生命周期会继续关闭维护任务。
    编写/修改日期（日志对应）：2026-10-03。
    """
    client_host = request.client.host if request.client else ''
    origin = request.headers.get('origin')
    if client_host not in {'127.0.0.1', '::1', 'localhost'}:
        return JSONResponse({'detail': '只允许本机退出系统'}, status_code=403)
    if origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse({'detail': '请求来源不受信任'}, status_code=403)
    if request.headers.get('x-local-exit') != 'kitchen-sentinel':
        return JSONResponse({'detail': '缺少本机退出标识'}, status_code=403)
    try:
        SHUTDOWN_MARKER.parent.mkdir(parents=True, exist_ok=True)
        SHUTDOWN_MARKER.write_text('local-ui\n', encoding='utf-8')
    except OSError:
        log.exception('cannot create local shutdown marker')
        return JSONResponse({'detail': '无法准备安全退出，请使用启动窗口中的 Ctrl+C'}, status_code=503)

    # 延迟到响应发送之后触发，避免浏览器看到连接被服务端提前截断。
    asyncio.get_running_loop().call_later(0.15, lambda: signal.raise_signal(signal.SIGINT))
    return {'status': 'stopping'}


def authenticated_snapshot(token, scope='hardware'):
    """在独立数据库会话中读取 WebSocket 用户的快照。
    编写/修改日期（日志对应）：2026-10-03。
    """
    with SessionLocal() as db:
        session = db.get(AuthSession, digest(token))
        if not session or session.expires_at <= utcnow():
            return None
        user = db.get(User, session.user_id)
        if not user or not user.active:
            return None
        return snapshot(db, scope)


@app.websocket('/api/v1/live')
async def live(ws: WebSocket):
    """提交后立即推送快照，并以一秒心跳更新在线状态；断线和过期会话主动关闭。

    用会话 Cookie 校验用户和来源，在线程池查询快照并按周期推送；连接退出时停止循环并释放上下文。
    编写/修改日期（日志对应）：2026-10-03。
    """
    if ws.headers.get('origin') not in ALLOWED_ORIGINS:
        await ws.close(code=1008)
        return
    token = ws.cookies.get('ks_session', '')
    if not token:
        await ws.close(code=1008)
        return
    await ws.accept()
    scope = ws.query_params.get('scope', 'hardware')
    if scope not in ('hardware', 'simulated', 'all'):
        await ws.close(code=1008)
        return
    revision = updates.revision
    try:
        while True:
            data = await asyncio.to_thread(authenticated_snapshot, token, scope)
            if data is None:
                await ws.close(code=1008)
                return
            await ws.send_text(json.dumps(data, ensure_ascii=False))
            revision = await asyncio.to_thread(updates.wait, revision)
            # 日志对应：2026-10-13。合并一次事务中的密集变更，避免连发重复全量快照。
            await asyncio.sleep(0.05)
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        # 浏览器主动关闭、服务重启或任务取消都属于正常连接生命周期。
        pass
    except SQLAlchemyError:
        await ws.close(code=1011)


@app.api_route('/api/{unknown_path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
def unknown_api(unknown_path: str):
    """日志对应：2026-10-12。未知 API 不落到静态文件服务，给出可诊断的中文 404。"""
    return JSONResponse({'detail': '接口不存在或服务版本尚未更新，请刷新页面并检查当前启动版本',
                         'path': '/api/' + unknown_path}, status_code=404)


frontend = PROJECT_ROOT / 'frontend' / 'dist'
if frontend.exists():
    app.mount('/', StaticFiles(directory=Path(frontend), html=True), name='frontend')

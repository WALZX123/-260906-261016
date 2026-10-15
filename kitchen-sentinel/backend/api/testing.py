"""文件职责：本机系统测试服务的生命周期接口。
主要功能：操作员启停独立模拟器，检查归属，服务退出时清理本接口创建的进程。
技术栈：FastAPI、subprocess、线程锁、本机回环地址校验。
模块联动：系统测试页调用，模拟器使用独立节点；不操作硬件采集进程。
编写/修改日期（日志对应）：2026-10-09、2026-10-12。
"""
import subprocess
import sys
from threading import Lock
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from backend.api.dependencies import current_user, operator
from backend.core.config import PROJECT_ROOT, settings
from backend.core.db import get_db
from backend.models import Device, utcnow
from backend.services.monitoring import audit

router = APIRouter(prefix='/testing/simulator', tags=['系统测试'])
lock = Lock()
process = None


def process_running():
    """日志对应：2026-10-09。只查本模块保存的进程句柄，不按名称查杀其他 Python。"""
    return process is not None and process.poll() is None


@router.get('')
def status(user=Depends(current_user), db=Depends(get_db, scope='function')):
    """日志对应：2026-10-09。分别报告托管进程与心跳，识别外部启动的模拟器。"""
    device = db.scalar(select(Device).where(Device.source == 'simulated').order_by(Device.id))
    online = bool(device and device.last_seen and (utcnow() - device.last_seen).total_seconds() < 6)
    return {'managed': process_running(), 'online': online}


@router.post('/start')
def start(request: Request, user=Depends(operator), db=Depends(get_db, scope='function')):
    """日志对应：2026-10-09。限制受信任本机地址，避免把设备令牌发往未知主机。"""
    global process
    base = str(request.base_url).rstrip('/')
    allowed = {origin.strip() for origin in settings().allowed_origins.split(',')}
    if request.url.hostname not in ('localhost', '127.0.0.1', '::1') or base not in allowed:
        raise HTTPException(403, '模拟测试进程只允许通过受信任的本机地址启动')
    with lock:
        if process_running() or status(user, db)['online']:
            return {'status': 'running'}
        log_path = PROJECT_ROOT / '.runtime' / 'system-test-simulator.log'
        with log_path.open('ab') as output:
            process = subprocess.Popen([sys.executable, '-m', 'simulator.main', '--url', base],
                cwd=PROJECT_ROOT, stdout=output, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        audit(db, user.username, 'testing.simulator.start', 'kitchen-001')
    return {'status': 'starting'}


def stop_owned():
    """日志对应：2026-10-09。只回收本接口创建的模拟器，超时才终止该句柄对应进程。"""
    global process
    with lock:
        if process_running():
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        process = None


@router.post('/stop')
def stop(user=Depends(operator), db=Depends(get_db, scope='function')):
    """日志对应：2026-10-09。停止托管进程并留审计，不关闭从其他位置启动的模拟器。"""
    if not process_running():
        raise HTTPException(409, '没有由系统测试页面启动的模拟器，请在原启动位置停止')
    stop_owned()
    audit(db, user.username, 'testing.simulator.stop', 'kitchen-001')
    return {'status': 'stopped'}

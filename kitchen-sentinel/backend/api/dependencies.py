"""文件职责：请求认证与权限边界。
主要功能：解析用户会话、校验写请求 CSRF，限制操作员、管理员和设备访问。
技术栈：FastAPI Depends、SQLAlchemy、摘要认证。
模块联动：auth 和 platform 路由复用用户权限，devices 路由复用独立设备令牌认证。
编写/修改日期（日志对应）：2026-09-30；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""

import hmac
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from backend.core.db import get_db
from backend.core.security import digest
from backend.models import AuthSession, User, Device, utcnow


def current_user(request: Request, db: Session = Depends(get_db, scope='function')):
    """从 HttpOnly Cookie 找到用户，并为写请求校验 CSRF 令牌。
    编写/修改日期（日志对应）：2026-09-30。
    """
    token = request.cookies.get('ks_session', '')
    session = db.get(AuthSession, digest(token)) if token else None
    if not session or session.expires_at <= utcnow():
        raise HTTPException(401, '请先登录或重新登录')
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, '账号不可用')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), session.csrf_token):
            raise HTTPException(403, '请求校验失败，请刷新后重试')
    request.state.session = session
    return user


def operator(user=Depends(current_user)):
    """允许操作员和管理员执行控制、报警确认等写操作。
    编写/修改日期（日志对应）：2026-09-30。
    """
    if user.role not in ('operator', 'admin'):
        raise HTTPException(403, '需要操作员或管理员权限')
    return user


def admin(user=Depends(current_user)):
    """只允许管理员执行账号和规则管理。
    编写/修改日期（日志对应）：2026-09-30。
    """
    if user.role != 'admin':
        raise HTTPException(403, '需要管理员权限')
    return user


def device_auth(device_id: str, request: Request, db: Session = Depends(get_db, scope='function')):
    """校验设备 Bearer 令牌；数据库只比较令牌摘要。
    编写/修改日期（日志对应）：2026-09-30。
    """
    device = db.get(Device, device_id)
    token = request.headers.get('authorization', '').removeprefix('Bearer ')
    if not device or not hmac.compare_digest(device.token_hash, digest(token)):
        raise HTTPException(401, '设备身份验证失败')
    return device

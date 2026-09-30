"""登录、登出和用户管理接口。"""

import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from backend.core.db import get_db
from backend.core.config import settings
from backend.core.security import verify_password, digest, hash_password
from backend.models import User, AuthSession, utcnow
from backend.schemas import LoginInput, UserInput
from backend.api.dependencies import current_user, admin
from backend.services.monitoring import audit

router = APIRouter(prefix='/auth', tags=['账号与权限'])
attempts = defaultdict(deque)


def _client_key(request: Request) -> str:
    """取得限流来源；测试客户端可能没有地址，不能因此让登录接口报错。"""

    return request.client.host if request.client else 'unknown-client'


@router.post('/login')
def login(data: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    """创建八小时会话，并返回只用于后续写请求的 CSRF 令牌。"""
    # 登录限流按来源地址做轻量保护；生产部署时可在反向代理再加一层全局限流。
    origin = request.headers.get('origin')
    allowed_origins = {item.strip() for item in settings().allowed_origins.split(',') if item.strip()}
    if origin and origin not in allowed_origins:
        raise HTTPException(403, '不允许的登录来源')
    key = _client_key(request)
    now = time.monotonic()
    bucket = attempts[key]
    while bucket and bucket[0] < now - 60:
        bucket.popleft()
    if len(bucket) >= 10:
        raise HTTPException(429, '尝试次数过多，请一分钟后重试')
    bucket.append(now)
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not user.active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, '用户名或密码不正确')
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    db.add(AuthSession(token_hash=digest(token), user_id=user.id, csrf_token=csrf,
                       expires_at=utcnow() + timedelta(hours=8)))
    audit(db, user.username, 'auth.login')
    response.set_cookie('ks_session', token, httponly=True, secure=settings().cookie_secure,
                        samesite='strict', max_age=8 * 3600)
    return {'username': user.username, 'role': user.role, 'csrf_token': csrf}


@router.get('/me')
def me(request: Request, user=Depends(current_user)):
    """返回当前用户信息，前端刷新页面时用它恢复登录状态。"""
    return {'username': user.username, 'role': user.role, 'csrf_token': request.state.session.csrf_token}


@router.post('/logout')
def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
    """删除服务端会话并让浏览器删除 Cookie。"""
    db.delete(request.state.session)
    response.delete_cookie('ks_session')
    return {'ok': True}


@router.get('/users')
def users(user=Depends(admin), db=Depends(get_db)):
    """列出用户基本资料，永远不返回密码摘要。"""
    return [{'id': u.id, 'username': u.username, 'role': u.role, 'active': u.active} for u in db.scalars(select(User))]


@router.post('/users', status_code=201)
def add_user(data: UserInput, user=Depends(admin), db=Depends(get_db)):
    """由管理员创建新的平台用户。"""
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(409, '用户名已存在')
    new = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(new)
    audit(db, user.username, 'user.create', data.username, role=data.role)
    return {'username': data.username, 'role': data.role}

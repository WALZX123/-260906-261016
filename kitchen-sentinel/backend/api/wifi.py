"""文件职责：本机 Wi-Fi 配置接口。
主要功能：可写角色配置热点和电脑地址，只返回脱敏状态；待机才能改连接。
技术栈：FastAPI、Pydantic、私有 JSON、原子替换；模块联动：设备启用页、SWD 配置、TCP 网关。
编写/修改日期（日志对应）：2026-09-30、2026-10-15。
"""
import ipaddress
import json
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from backend.api.dependencies import current_user, operator
from backend.core.config import PROJECT_ROOT
from backend.core.db import get_db
from backend.models import Device
from backend.services.monitoring import audit

router = APIRouter(tags=['无线连接'])
CONFIG = PROJECT_ROOT / '.runtime/wifi.json'


class WifiInput(BaseModel):
    """日志对应：2026-10-15。限制 AT 特殊字符和地址，防止配置文本成为额外指令。"""
    ssid: str = Field(min_length=1, max_length=32)
    password: str = Field(max_length=63)
    host: str = Field(max_length=15)

    @field_validator('ssid', 'password')
    @classmethod
    def safe_at(cls, value):
        """校验 UTF-8 字节数和 AT 分隔符；密码只用于本机写配置，不在响应中返回。"""
        if any(c in value for c in '\r\n"\\') or len(value.encode()) > 63:
            raise ValueError('热点配置不能包含换行、双引号或反斜杠')
        return value

    @field_validator('host')
    @classmethod
    def local_address(cls, value):
        """只连接本机局域网 IPv4 地址；Wi-Fi 端口固定为 9000。"""
        addr = ipaddress.IPv4Address(value)
        if not addr.is_private or addr.is_loopback or addr.is_unspecified:
            raise ValueError('请填写电脑在热点网络中的 IPv4 地址')
        return str(addr)


@router.get('/wifi')
def status(user=Depends(current_user)):
    """返回热点名和地址供页面核对，永不返回密码或设备认证密钥。日期：2026-10-15。"""
    try:
        data = json.loads(CONFIG.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    return {'configured': bool(data), 'ssid': data.get('ssid', ''), 'host': data.get('host', ''), 'port': 9000}


@router.post('/wifi')
def configure(data: WifiInput, user=Depends(operator), db=Depends(get_db, scope='function')):
    """待机时原子保存私有设置；SWD 将其写入 RAM，TCP 网关用独立随机密钥认证。日期：2026-10-15。"""
    if len(data.ssid.encode()) > 32 or (data.password and len(data.password) < 8):
        raise HTTPException(422, '热点名最多 32 字节，有密码热点的密码至少 8 位')
    for device in db.scalars(select(Device).where(Device.source == 'hardware')):
        if (device.latest or {}).get('monitoring_enabled') is True:
            raise HTTPException(409, '请先暂停设备采样，再更改无线连接')
    CONFIG.parent.mkdir(exist_ok=True)
    payload = {**data.model_dump(), 'token': secrets.token_hex(24), 'revision': time.time_ns() % 0xFFFFFFFF or 1}
    temporary = CONFIG.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    temporary.replace(CONFIG)
    audit(db, user.username, 'wifi.configure', 'stm32-001', ssid=data.ssid, host=data.host)
    return {'configured': True, 'ssid': data.ssid, 'host': data.host, 'port': 9000}

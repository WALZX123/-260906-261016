"""文件职责：数据库实体与持久化结构。
主要功能：定义用户、会话、设备、遥测、报警、命令、规则和审计实体及索引。
技术栈：Python 类型注解、SQLAlchemy ORM、MySQL JSON/DateTime。
模块联动：API 和 monitoring 读写实体，Alembic 按 Base 元数据迁移；时间统一按 UTC 存储，恢复不删除报警。
编写/修改日期（日志对应）：2026-10-01。
"""

from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.core.db import Base


def utcnow():
    """返回当前 UTC 时间，并去掉时区信息以匹配 MySQL DateTime。
    编写/修改日期（日志对应）：2026-10-01。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """平台用户及其角色。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='viewer')
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthSession(Base):
    """登录会话；只保存会话令牌摘要和 CSRF 令牌。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Device(Base):
    """设备注册信息和最近一次设备状态。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'devices'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(20), default='simulated')
    token_hash: Mapped[str] = mapped_column(String(64))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latest: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    actuators: Mapped[dict] = mapped_column(JSON, default=dict)
    scenario: Mapped[str] = mapped_column(String(32), default='normal')
    scenario_revision: Mapped[int] = mapped_column(Integer, default=0)
    firmware: Mapped[str] = mapped_column(String(64), default='simulator/1.0')


class Telemetry(Base):
    """设备遥测历史；设备启动编号与序号组成幂等键。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'telemetry'
    __table_args__ = (UniqueConstraint('device_id', 'boot_id', 'sequence', name='uq_sample'),
                     Index('ix_telemetry_device_time', 'device_id', 'received_at'))
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey('devices.id'))
    boot_id: Mapped[str] = mapped_column(String(64))
    sequence: Mapped[int] = mapped_column(Integer)
    sampled_at: Mapped[datetime] = mapped_column(DateTime)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    gas: Mapped[float | None] = mapped_column(Float, nullable=True)
    smoke: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    flame: Mapped[bool] = mapped_column(Boolean)
    valid: Mapped[bool] = mapped_column(Boolean, default=True)
    local_alarm: Mapped[str] = mapped_column(String(32), default='normal')
    # 日志对应：2026-10-15。演练、待机、来源和原始量随历史保存，旧记录上下文为空。
    sample_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Alarm(Base):
    """报警生命周期和可追溯时间线。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'alarms'
    __table_args__ = (Index('ix_alarm_device_status', 'device_id', 'status'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey('devices.id'))
    kind: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default='active')
    message: Mapped[str] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Command(Base):
    """控制命令及其下发、回执、超时状态。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'commands'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey('devices.id'), index=True)
    action: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    requested_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result: Mapped[str | None] = mapped_column(String(500), nullable=True)


class RuleConfig(Base):
    """当前生效的报警规则版本。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'rule_configs'
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    values: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    """关键操作审计记录。
    编写/修改日期（日志对应）：2026-10-01。
    """
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

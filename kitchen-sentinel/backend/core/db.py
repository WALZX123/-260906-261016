"""文件职责：数据库连接和事务入口。
主要功能：建立连接池与 ORM 基类，为请求提供提交、回滚和关闭会话。
技术栈：Python、SQLAlchemy 2、MySQL/PyMySQL。
模块联动：models 继承 Base，API 使用 get_db，迁移与维护任务使用同一数据库配置。
编写/修改日期（日志对应）：2026-10-01；2026-10-12（回归与边界修正）、2026-10-13（实时与联调优化）。
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from backend.core.config import settings
from backend.services.live import updates


class Base(DeclarativeBase):
    """所有 ORM 模型继承的声明式基类。
    编写/修改日期（日志对应）：2026-10-01。
    """

    pass


# 本地演示也按持续采样的服务来配置连接池：10 条常驻连接应对页面刷新、WebSocket
# 快照和模拟器并发写入，最多临时扩展 20 条。LIFO 可以优先复用刚使用过的连接，
# 配合 pre_ping/recycle 降低 MySQL 空闲连接失效导致的偶发 500。
engine = create_engine(
    settings().database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    pool_timeout=10,
    pool_use_lifo=True,
    connect_args={'connect_timeout': 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, 'after_flush')
def track_live_change(db, context):
    """日志对应：2026-10-13。记住本事务发生写入，查询和空维护事务不触发广播。"""
    if db.new or db.dirty or db.deleted:
        db.info['live_changed'] = True


@event.listens_for(Session, 'after_commit')
def publish_committed_change(db):
    """日志对应：2026-10-13。提交成功才发布更新，防止页面读到旧事务或失败操作。"""
    if db.info.pop('live_changed', False):
        updates.publish()


@event.listens_for(Session, 'after_rollback')
def discard_live_change(db):
    """日志对应：2026-10-13。回滚时丢弃待发布标记，不把失败操作广播为成功。"""
    db.info.pop('live_changed', None)


def get_db() -> Generator:
    """为一次 HTTP 请求提供一个会话，并保证异常时回滚。
    编写/修改日期（日志对应）：2026-10-01。
    """

    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

"""数据库引擎、模型基类和请求级会话。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from backend.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型继承的声明式基类。"""

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


def get_db() -> Generator:
    """为一次 HTTP 请求提供一个会话，并保证异常时回滚。"""

    with SessionLocal() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

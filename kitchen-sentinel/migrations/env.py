"""文件职责：数据库迁移运行环境。
主要功能：按离线或在线方式配置 Alembic 事务和 ORM 元数据。
技术栈：Alembic context、SQLAlchemy engine、Base.metadata。
模块联动：加载 backend.models 取得全部实体，bootstrap 执行迁移时使用本文件，与业务请求事务分开。
编写/修改日期（日志对应）：2026-09-30。
"""

from alembic import context
from backend.core.db import engine, Base
import backend.models  # noqa: F401

if context.is_offline_mode():
    context.configure(url=engine.url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

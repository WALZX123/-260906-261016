"""文件职责：账号通知偏好持久化迁移。
主要功能：为现有用户增加可空JSON设置，不删除或重写账号、采样与报警。
技术栈：Alembic、SQLAlchemy；关联User及本人通知设置接口。
编写/修改日期（日志对应）：2026-10-16。
"""
from alembic import op
import sqlalchemy as sa

revision = '20261016_notifications'
down_revision = '20261015_reports'
branch_labels = depends_on = None


def upgrade():
    """空值由业务代码解释为默认开启，保留现有账号状态。"""
    op.add_column('users', sa.Column('notification_preferences', sa.JSON(), nullable=True))


def downgrade():
    """移除本版本偏好列；回退会丢失个人提醒设置，应先导出。"""
    op.drop_column('users', 'notification_preferences')

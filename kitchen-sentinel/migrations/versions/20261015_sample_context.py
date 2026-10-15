"""文件职责：遥测演练及待机上下文迁移。
主要功能：新增可空 JSON，旧记录保持未知，不反推旧数据属于演练或真实采样。
技术栈：Alembic、SQLAlchemy；模块联动：Telemetry、历史查询与 CSV。
编写/修改日期（日志对应）：2026-10-01、2026-10-15。
"""
from alembic import op
import sqlalchemy as sa

revision = '20261015_context'
down_revision = '61f91196cf18'
branch_labels = None
depends_on = None


def upgrade():
    """增加上下文列；保留原始值、演练来源和待机标志，不改写历史测量。"""
    op.add_column('telemetry', sa.Column('sample_context', sa.JSON(), nullable=True))


def downgrade():
    """回退只移除本版本新增上下文；生产数据回退需先另行保存该列。"""
    op.drop_column('telemetry', 'sample_context')

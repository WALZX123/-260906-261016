"""文件职责：运行报告与离线回放状态迁移。
主要功能：新增报告快照及设备启动级回放游标；技术栈：Alembic、SQLAlchemy。
模块联动：OperationReport、ReplayState；编写/修改日期（日志对应）：2026-10-15。
"""
from alembic import op
import sqlalchemy as sa

revision = '20261015_reports'
down_revision = '20261015_context'
branch_labels = depends_on = None


def upgrade():
    """创建独立业务表，不改写已有采样和报警。"""
    op.create_index('ix_telemetry_device_sampled', 'telemetry', ['device_id', 'sampled_at'])
    op.create_table('operation_reports', sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('period', sa.String(16), nullable=False), sa.Column('device_id', sa.String(64), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('starts_at', sa.DateTime(), nullable=False), sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('created_by', sa.String(64), nullable=False),
        sa.Column('facts', sa.JSON(), nullable=False), sa.Column('analysis', sa.JSON(), nullable=False))
    op.create_table('replay_states', sa.Column('device_id', sa.String(64), sa.ForeignKey('devices.id'), primary_key=True),
        sa.Column('boot_id', sa.String(64), primary_key=True), sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('active', sa.JSON(), nullable=False))


def downgrade():
    """回退前由维护人员导出报告和回放进度；本操作只删除本版本表。"""
    op.drop_index('ix_telemetry_device_sampled', table_name='telemetry')
    op.drop_table('replay_states')
    op.drop_table('operation_reports')

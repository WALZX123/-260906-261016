"""文件职责：数据库初始结构版本。
主要功能：建立核心业务表与索引，提供对应的结构回退步骤。
技术栈：Alembic op、SQLAlchemy 类型与约束。
模块联动：由 migrations.env 和 bootstrap 执行，表结构与 backend.models 对应；回退会删除本版本表，须按实际迁移操作使用。
编写/修改日期（日志对应）：2026-09-30。
"""
from alembic import op
import sqlalchemy as sa

revision = '61f91196cf18'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 正向迁移：按模型依赖建立业务表、外键和查询索引。
    """按版本顺序创建初始业务表、外键与索引；由 Alembic 在独立迁移事务中执行。
    编写/修改日期（日志对应）：2026-09-30。
    """
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('target', sa.String(length=128), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_table('devices',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('location', sa.String(length=100), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('last_seen', sa.DateTime(), nullable=True),
    sa.Column('latest', sa.JSON(), nullable=False),
    sa.Column('evaluation', sa.JSON(), nullable=False),
    sa.Column('actuators', sa.JSON(), nullable=False),
    sa.Column('scenario', sa.String(length=32), nullable=False),
    sa.Column('scenario_revision', sa.Integer(), nullable=False),
    sa.Column('firmware', sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('rule_configs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('values', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('alarms',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('message', sa.String(length=500), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('recovered_at', sa.DateTime(), nullable=True),
    sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
    sa.Column('acknowledged_by', sa.String(length=64), nullable=True),
    sa.Column('timeline', sa.JSON(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('analysis', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alarm_device_status', 'alarms', ['device_id', 'status'], unique=False)
    op.create_index(op.f('ix_alarms_started_at'), 'alarms', ['started_at'], unique=False)
    op.create_table('auth_sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index(op.f('ix_auth_sessions_expires_at'), 'auth_sessions', ['expires_at'], unique=False)
    op.create_table('commands',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('requested_by', sa.String(length=64), nullable=False),
    sa.Column('idempotency_key', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('result', sa.String(length=500), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_index(op.f('ix_commands_device_id'), 'commands', ['device_id'], unique=False)
    op.create_table('telemetry',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('boot_id', sa.String(length=64), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('sampled_at', sa.DateTime(), nullable=False),
    sa.Column('received_at', sa.DateTime(), nullable=False),
    sa.Column('gas', sa.Float(), nullable=True),
    sa.Column('smoke', sa.Float(), nullable=True),
    sa.Column('temperature', sa.Float(), nullable=True),
    sa.Column('flame', sa.Boolean(), nullable=False),
    sa.Column('valid', sa.Boolean(), nullable=False),
    sa.Column('local_alarm', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('device_id', 'boot_id', 'sequence', name='uq_sample')
    )
    op.create_index('ix_telemetry_device_time', 'telemetry', ['device_id', 'received_at'], unique=False)
    # 初始结构建立结束，事务由迁移运行环境统一提交。

def downgrade():
    # 反向迁移：先删除依赖索引和关联表，再回退基础表。
    """按依赖反序删除本版本索引与表，供显式结构回退使用，不在正常业务请求中调用。
    编写/修改日期（日志对应）：2026-09-30。
    """
    op.drop_index('ix_telemetry_device_time', table_name='telemetry')
    op.drop_table('telemetry')
    op.drop_index(op.f('ix_commands_device_id'), table_name='commands')
    op.drop_table('commands')
    op.drop_index(op.f('ix_auth_sessions_expires_at'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
    op.drop_index(op.f('ix_alarms_started_at'), table_name='alarms')
    op.drop_index('ix_alarm_device_status', table_name='alarms')
    op.drop_table('alarms')
    op.drop_table('users')
    op.drop_table('rule_configs')
    op.drop_table('devices')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_table('audit_logs')
    # 本版本结构回退结束，正常业务流程不会调用此步骤。

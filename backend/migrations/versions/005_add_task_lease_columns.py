"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - 租约字段迁移

添加租约相关列：lease_acquired_at, lease_expires_at, lease_updated_at
Revision ID: 005_add_task_lease_columns
Revises: 004_init_task_tables
Create Date: 2026-04-28

"""
import sqlalchemy as sa
from alembic import op

revision = "005_add_task_lease_columns"
down_revision = "004_init_task_tables"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tasks')]
    
    if 'lease_acquired_at' not in columns:
        op.add_column('tasks', sa.Column('lease_acquired_at', sa.DateTime(), nullable=True, comment='租约获取时间'))
    
    if 'lease_expires_at' not in columns:
        op.add_column('tasks', sa.Column('lease_expires_at', sa.DateTime(), nullable=True, comment='租约过期时间'))
        op.create_index(op.f('ix_tasks_lease_expires_at'), 'tasks', ['lease_expires_at'], unique=False)
    
    if 'lease_updated_at' not in columns:
        op.add_column('tasks', sa.Column('lease_updated_at', sa.DateTime(), nullable=True, comment='最后租约更新时间'))
    
    if 'standard_file_id' in columns and 'ix_tasks_standard_file_id' not in [i['name'] for i in inspector.get_indexes('tasks')]:
        op.create_index(op.f('ix_tasks_standard_file_id'), 'tasks', ['standard_file_id'], unique=False)
    
    if 'rule_template_id' in columns and 'ix_tasks_rule_template_id' not in [i['name'] for i in inspector.get_indexes('tasks')]:
        op.create_index(op.f('ix_tasks_rule_template_id'), 'tasks', ['rule_template_id'], unique=False)
    
    if 'worker_id' in columns and 'ix_tasks_worker_id' not in [i['name'] for i in inspector.get_indexes('tasks')]:
        op.create_index(op.f('ix_tasks_worker_id'), 'tasks', ['worker_id'], unique=False)
    
    if 'is_active' in columns and 'ix_tasks_is_active' not in [i['name'] for i in inspector.get_indexes('tasks')]:
        op.create_index(op.f('ix_tasks_is_active'), 'tasks', ['is_active'], unique=False)
    
    if 'is_archived' in columns and 'ix_tasks_is_archived' not in [i['name'] for i in inspector.get_indexes('tasks')]:
        op.create_index(op.f('ix_tasks_is_archived'), 'tasks', ['is_archived'], unique=False)
    
    # 补充 task_events 表缺失的索引
    event_indexes = [i['name'] for i in inspector.get_indexes('task_events')]
    
    if 'worker_id' in [c['name'] for c in inspector.get_columns('task_events')]:
        if 'ix_task_events_worker_id' not in event_indexes:
            op.create_index(op.f('ix_task_events_worker_id'), 'task_events', ['worker_id'], unique=False)
    
    if 'error_code' in [c['name'] for c in inspector.get_columns('task_events')]:
        if 'ix_task_events_error_code' not in event_indexes:
            op.create_index(op.f('ix_task_events_error_code'), 'task_events', ['error_code'], unique=False)
    
    if 'step_name' in [c['name'] for c in inspector.get_columns('task_events')]:
        if 'ix_task_events_step_name' not in event_indexes:
            op.create_index(op.f('ix_task_events_step_name'), 'task_events', ['step_name'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = [i['name'] for i in inspector.get_indexes('tasks')]
    
    if 'ix_tasks_lease_expires_at' in indexes:
        op.drop_index(op.f('ix_tasks_lease_expires_at'), table_name='tasks')
    
    columns = [c['name'] for c in inspector.get_columns('tasks')]
    if 'lease_updated_at' in columns:
        op.drop_column('tasks', 'lease_updated_at')
    if 'lease_expires_at' in columns:
        op.drop_column('tasks', 'lease_expires_at')
    if 'lease_acquired_at' in columns:
        op.drop_column('tasks', 'lease_acquired_at')

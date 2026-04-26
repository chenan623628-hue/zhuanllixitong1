"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - 数据库迁移

创建任务表、任务事件表
Revision ID: 004_init_task_tables
Revises: 003_init_file_tables
Create Date: 2026-04-25 20:00:00

"""
import sqlalchemy as sa
from alembic import op

revision = "004_init_task_tables"
down_revision = "003_init_file_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_id", sa.String(length=64), nullable=False, comment="任务唯一标识 UUID"),
        sa.Column("task_type", sa.String(length=16), nullable=False, comment="任务类型：1:1/N:1"),
        sa.Column("task_name", sa.String(length=256), nullable=False, comment="任务名称"),
        sa.Column("task_description", sa.Text(), nullable=True, comment="任务描述"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="任务状态"),
        sa.Column("previous_status", sa.String(length=32), nullable=True, comment="上一状态"),
        sa.Column("priority", sa.Integer(), nullable=False, comment="优先级"),
        sa.Column("patent_file_id", sa.String(length=64), nullable=True, comment="专利文件ID"),
        sa.Column("patent_file_ids", sa.Text(), nullable=True, comment="专利文件ID列表 JSON"),
        sa.Column("standard_file_id", sa.String(length=64), nullable=False, comment="标准文件ID"),
        sa.Column("rule_template_id", sa.String(length=64), nullable=True, comment="规则模板ID"),
        sa.Column("user_id", sa.Integer(), nullable=True, comment="创建用户ID"),
        sa.Column("created_ip", sa.String(length=64), nullable=True, comment="创建IP地址"),
        sa.Column("created_source", sa.String(length=64), nullable=True, comment="创建来源"),
        sa.Column("queued_at", sa.DateTime(), nullable=True, comment="入队时间"),
        sa.Column("started_at", sa.DateTime(), nullable=True, comment="开始执行时间"),
        sa.Column("parsing_completed_at", sa.DateTime(), nullable=True, comment="解析完成时间"),
        sa.Column("comparing_completed_at", sa.DateTime(), nullable=True, comment="比对完成时间"),
        sa.Column("review_completed_at", sa.DateTime(), nullable=True, comment="人工校验完成时间"),
        sa.Column("report_completed_at", sa.DateTime(), nullable=True, comment="报告生成完成时间"),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="最终完成时间"),
        sa.Column("failed_at", sa.DateTime(), nullable=True, comment="失败时间"),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True, comment="取消时间"),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=True, comment="预估耗时"),
        sa.Column("actual_duration_seconds", sa.Integer(), nullable=True, comment="实际耗时"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, comment="进度百分比"),
        sa.Column("progress_message", sa.String(length=512), nullable=True, comment="进度描述"),
        sa.Column("retry_count", sa.Integer(), nullable=False, comment="重试次数"),
        sa.Column("max_retries", sa.Integer(), nullable=False, comment="最大重试次数"),
        sa.Column("error_code", sa.String(length=64), nullable=True, comment="错误码"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("error_traceback", sa.Text(), nullable=True, comment="错误堆栈"),
        sa.Column("worker_id", sa.String(length=64), nullable=True, comment="Worker实例ID"),
        sa.Column("worker_version", sa.String(length=32), nullable=True, comment="Worker版本号"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, comment="是否已归档"),
        sa.Column("metadata", sa.Text(), nullable=True, comment="扩展元数据"),
        sa.Column("tags", sa.Text(), nullable=True, comment="标签列表"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
        comment="比对任务主表",
    )
    op.create_index(op.f("ix_tasks_task_id"), "tasks", ["task_id"], unique=True)
    op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_created_at"), "tasks", ["created_at"], unique=False)
    op.create_index(op.f("ix_tasks_priority"), "tasks", ["priority"], unique=False)
    
    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_id", sa.String(length=64), nullable=False, comment="事件唯一标识"),
        sa.Column("event_type", sa.String(length=64), nullable=False, comment="事件类型"),
        sa.Column("event_time", sa.DateTime(), nullable=False, comment="事件时间"),
        sa.Column("task_id", sa.String(length=64), nullable=False, comment="关联任务ID"),
        sa.Column("from_status", sa.String(length=32), nullable=True, comment="转移前状态"),
        sa.Column("to_status", sa.String(length=32), nullable=True, comment="转移后状态"),
        sa.Column("event_message", sa.String(length=1024), nullable=True, comment="事件描述"),
        sa.Column("event_details", sa.Text(), nullable=True, comment="事件详情(JSON)"),
        sa.Column("progress_percent", sa.Integer(), nullable=True, comment="进度百分比"),
        sa.Column("progress_message", sa.String(length=512), nullable=True, comment="进度消息"),
        sa.Column("user_id", sa.Integer(), nullable=True, comment="触发事件的用户ID"),
        sa.Column("worker_id", sa.String(length=64), nullable=True, comment="触发事件的Worker ID"),
        sa.Column("error_code", sa.String(length=64), nullable=True, comment="错误码"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
        sa.Column("step_name", sa.String(length=128), nullable=True, comment="执行步骤名称"),
        sa.Column("step_duration_seconds", sa.Integer(), nullable=True, comment="步骤耗时"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        comment="任务事件日志表",
    )
    op.create_index(op.f("ix_task_events_event_id"), "task_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_task_events_task_id"), "task_events", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_events_event_time"), "task_events", ["event_time"], unique=False)
    op.create_index(op.f("ix_task_events_event_type"), "task_events", ["event_type"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_task_events_event_type"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_event_time"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_task_id"), table_name="task_events")
    op.drop_index(op.f("ix_task_events_event_id"), table_name="task_events")
    op.drop_table("task_events")
    
    op.drop_index(op.f("ix_tasks_priority"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_created_at"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_user_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_task_id"), table_name="tasks")
    op.drop_table("tasks")

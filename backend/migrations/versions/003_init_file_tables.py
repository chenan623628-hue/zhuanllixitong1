"""
专利-标准比对系统 V1.0
M04 文件上传与安全网关模块 - 数据库迁移

创建文件表、上传安全事件表
Revision ID: 003_init_file_tables
Revises: 002_init_rbac_tables
Create Date: 2026-04-25 10:00:00

"""
import sqlalchemy as sa
from alembic import op

revision = "003_init_file_tables"
down_revision = "002_init_rbac_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_id", sa.String(length=64), nullable=False, comment="文件唯一标识 UUID"),
        sa.Column("original_name", sa.String(length=256), nullable=False, comment="原始文件名"),
        sa.Column("stored_name", sa.String(length=256), nullable=False, comment="存储文件名"),
        sa.Column("file_path", sa.String(length=512), nullable=False, comment="文件存储路径"),
        sa.Column("file_type", sa.String(length=32), nullable=False, comment="文件类型：patent/standard/excel_import/other"),
        sa.Column("file_category", sa.String(length=32), nullable=True, comment="文件分类：pdf/word/excel/txt"),
        sa.Column("file_size", sa.Integer(), nullable=False, default=0, comment="文件大小(字节)"),
        sa.Column("page_count", sa.Integer(), nullable=True, comment="页数(PDF/Word)"),
        sa.Column("file_hash", sa.String(length=128), nullable=True, comment="文件哈希值(SHA256)"),
        sa.Column("mime_type", sa.String(length=128), nullable=True, comment="MIME类型"),
        sa.Column("file_extension", sa.String(length=16), nullable=True, comment="文件扩展名"),
        sa.Column("status", sa.String(length=32), nullable=False, default="pending", comment="文件状态"),
        sa.Column("scan_status", sa.String(length=32), nullable=True, default="pending", comment="安全扫描状态"),
        sa.Column("scan_result", sa.Text(), nullable=True, comment="扫描结果详情(JSON)"),
        sa.Column("scan_time", sa.DateTime(), nullable=True, comment="扫描完成时间"),
        sa.Column("upload_user_id", sa.Integer(), nullable=True, comment="上传用户ID"),
        sa.Column("upload_ip", sa.String(length=64), nullable=True, comment="上传IP地址"),
        sa.Column("upload_source", sa.String(length=64), nullable=True, comment="上传来源：web/api"),
        sa.Column("task_id", sa.String(length=64), nullable=True, comment="关联任务ID"),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True, comment="是否启用"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False, comment="是否已删除"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间"),
        sa.Column("metadata", sa.Text(), nullable=True, comment="扩展元数据(JSON)"),
        sa.Column("tags", sa.Text(), nullable=True, comment="标签列表(JSON数组)"),
        sa.ForeignKeyConstraint(["upload_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id"),
        comment="文件元数据表",
    )
    op.create_index(op.f("ix_files_file_id"), "files", ["file_id"], unique=True)
    op.create_index(op.f("ix_files_file_type"), "files", ["file_type"], unique=False)
    op.create_index(op.f("ix_files_file_hash"), "files", ["file_hash"], unique=False)
    op.create_index(op.f("ix_files_status"), "files", ["status"], unique=False)
    op.create_index(op.f("ix_files_upload_user_id"), "files", ["upload_user_id"], unique=False)
    op.create_index(op.f("ix_files_task_id"), "files", ["task_id"], unique=False)
    op.create_index(op.f("ix_files_is_deleted"), "files", ["is_deleted"], unique=False)
    
    op.create_table(
        "upload_security_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_id", sa.String(length=64), nullable=False, comment="事件唯一标识"),
        sa.Column("event_type", sa.String(length=64), nullable=False, comment="事件类型"),
        sa.Column("event_time", sa.DateTime(), nullable=False, comment="事件时间"),
        sa.Column("file_id", sa.String(length=64), nullable=True, comment="关联文件ID"),
        sa.Column("file_name", sa.String(length=256), nullable=True, comment="文件名"),
        sa.Column("file_size", sa.Integer(), nullable=True, comment="文件大小"),
        sa.Column("file_hash", sa.String(length=128), nullable=True, comment="文件哈希"),
        sa.Column("upload_user_id", sa.Integer(), nullable=True, comment="上传用户ID"),
        sa.Column("upload_ip", sa.String(length=64), nullable=True, comment="上传IP地址"),
        sa.Column("user_agent", sa.String(length=512), nullable=True, comment="用户代理"),
        sa.Column("severity", sa.String(length=32), nullable=False, default="info", comment="严重程度：info/warning/high/critical"),
        sa.Column("check_type", sa.String(length=64), nullable=True, comment="检测类型：file_type/size/virus/content"),
        sa.Column("check_result", sa.String(length=32), nullable=True, comment="检测结果：passed/failed/blocked"),
        sa.Column("check_details", sa.Text(), nullable=True, comment="检测详情(JSON)"),
        sa.Column("block_reason", sa.String(length=256), nullable=True, comment="阻断原因"),
        sa.Column("risk_score", sa.Integer(), nullable=True, comment="风险评分 0-100"),
        sa.Column("action_taken", sa.String(length=64), nullable=True, comment="采取的行动"),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, default=False, comment="是否被阻断"),
        sa.Column("metadata", sa.Text(), nullable=True, comment="扩展元数据(JSON)"),
        sa.ForeignKeyConstraint(["upload_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        comment="上传安全事件表",
    )
    op.create_index(op.f("ix_upload_security_events_event_id"), "upload_security_events", ["event_id"], unique=True)
    op.create_index(op.f("ix_upload_security_events_event_time"), "upload_security_events", ["event_time"], unique=False)
    op.create_index(op.f("ix_upload_security_events_file_id"), "upload_security_events", ["file_id"], unique=False)
    op.create_index(op.f("ix_upload_security_events_event_type"), "upload_security_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_upload_security_events_upload_user_id"), "upload_security_events", ["upload_user_id"], unique=False)
    op.create_index(op.f("ix_upload_security_events_severity"), "upload_security_events", ["severity"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_upload_security_events_severity"), table_name="upload_security_events")
    op.drop_index(op.f("ix_upload_security_events_upload_user_id"), table_name="upload_security_events")
    op.drop_index(op.f("ix_upload_security_events_event_type"), table_name="upload_security_events")
    op.drop_index(op.f("ix_upload_security_events_file_id"), table_name="upload_security_events")
    op.drop_index(op.f("ix_upload_security_events_event_time"), table_name="upload_security_events")
    op.drop_index(op.f("ix_upload_security_events_event_id"), table_name="upload_security_events")
    op.drop_table("upload_security_events")
    
    op.drop_index(op.f("ix_files_is_deleted"), table_name="files")
    op.drop_index(op.f("ix_files_task_id"), table_name="files")
    op.drop_index(op.f("ix_files_upload_user_id"), table_name="files")
    op.drop_index(op.f("ix_files_status"), table_name="files")
    op.drop_index(op.f("ix_files_file_hash"), table_name="files")
    op.drop_index(op.f("ix_files_file_type"), table_name="files")
    op.drop_index(op.f("ix_files_file_id"), table_name="files")
    op.drop_table("files")

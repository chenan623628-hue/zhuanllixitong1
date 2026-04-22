"""
专利-标准比对系统 V1.0
M02 认证模块 - 初始迁移

创建用户表、会话表、认证因子绑定表、认证挑战表
Revision ID: 001_init_auth_tables
Revises: 
Create Date: 2026-04-05 10:00:00

"""
import sqlalchemy as sa
from alembic import op

revision = "001_init_auth_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=False, comment="用户名"),
        sa.Column("email", sa.String(length=128), nullable=True, comment="邮箱"),
        sa.Column("phone", sa.String(length=32), nullable=True, comment="手机号"),
        sa.Column("password_hash", sa.String(length=256), nullable=False, comment="密码哈希"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否激活"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, comment="是否锁定"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True, comment="锁定时间"),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, comment="连续登录失败次数"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True, comment="最后登录时间"),
        sa.Column("last_login_ip", sa.String(length=64), nullable=True, comment="最后登录IP"),
        sa.Column("last_login_device", sa.String(length=256), nullable=True, comment="最后登录设备"),
        sa.Column("require_mfa", sa.Boolean(), nullable=False, comment="是否需要二阶段认证"),
        sa.Column("mfa_enabled_factors", sa.Text(), nullable=True, comment="已启用的认证因子（JSON数组）"),
        sa.Column("role", sa.String(length=32), nullable=False, comment="角色：user/auditor/security_admin/system_admin"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("username"),
        comment="用户表",
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False, comment="会话唯一标识"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="关联用户ID"),
        sa.Column("refresh_token_hash", sa.String(length=256), nullable=False, comment="Refresh Token 哈希"),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=False, comment="Access Token 过期时间"),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True), nullable=False, comment="Refresh Token 过期时间"),
        sa.Column("device_id", sa.String(length=64), nullable=True, comment="设备ID"),
        sa.Column("device_name", sa.String(length=128), nullable=True, comment="设备名称"),
        sa.Column("device_type", sa.String(length=32), nullable=True, comment="设备类型：web/mobile/desktop"),
        sa.Column("device_os", sa.String(length=64), nullable=True, comment="操作系统"),
        sa.Column("device_browser", sa.String(length=64), nullable=True, comment="浏览器"),
        sa.Column("ip_address", sa.String(length=64), nullable=True, comment="登录IP地址"),
        sa.Column("location", sa.String(length=128), nullable=True, comment="登录位置"),
        sa.Column("user_agent", sa.Text(), nullable=True, comment="完整User-Agent"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, comment="会话是否有效"),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True, comment="失效时间"),
        sa.Column("invalidated_reason", sa.String(length=128), nullable=True, comment="失效原因：logout/token_revoked/admin_action"),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, comment="最后活跃时间"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        comment="会话表",
    )
    op.create_index(op.f("ix_sessions_session_id"), "sessions", ["session_id"], unique=True)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_sessions_device_id"), "sessions", ["device_id"], unique=False)
    op.create_index(op.f("ix_sessions_is_valid"), "sessions", ["is_valid"], unique=False)
    
    op.create_table(
        "auth_factor_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="关联用户ID"),
        sa.Column("factor_type", sa.String(length=32), nullable=False, comment="因子类型：password/totp/sms/email/ukey"),
        sa.Column("factor_name", sa.String(length=64), nullable=True, comment="自定义名称"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, comment="是否已验证"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, comment="是否为主要因子"),
        sa.Column("config_data", sa.Text(), nullable=True, comment="配置数据（JSON格式）"),
        sa.Column("extra_metadata", sa.Text(), nullable=True, comment="元数据（JSON格式）"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最后使用时间"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True, comment="最后验证成功时间"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="认证因子绑定表",
    )
    op.create_index(op.f("ix_auth_factor_bindings_user_id"), "auth_factor_bindings", ["user_id"], unique=False)
    op.create_index(op.f("ix_auth_factor_bindings_factor_type"), "auth_factor_bindings", ["factor_type"], unique=False)
    
    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="关联用户ID"),
        sa.Column("session_id", sa.String(length=64), nullable=True, comment="会话ID"),
        sa.Column("challenge_id", sa.String(length=64), nullable=False, comment="挑战唯一标识"),
        sa.Column("challenge_type", sa.String(length=32), nullable=False, comment="挑战类型：totp/sms/email/ukey"),
        sa.Column("challenge_data", sa.Text(), nullable=True, comment="挑战数据（JSON格式）"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="状态：pending/success/failed/expired"),
        sa.Column("attempts", sa.Integer(), nullable=False, comment="尝试次数"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, comment="最大尝试次数"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="过期时间"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
        sa.Column("device_id", sa.String(length=64), nullable=True, comment="设备ID"),
        sa.Column("ip_address", sa.String(length=64), nullable=True, comment="IP地址"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id"),
        comment="认证挑战记录表",
    )
    op.create_index(op.f("ix_auth_challenges_challenge_id"), "auth_challenges", ["challenge_id"], unique=True)
    op.create_index(op.f("ix_auth_challenges_user_id"), "auth_challenges", ["user_id"], unique=False)
    op.create_index(op.f("ix_auth_challenges_session_id"), "auth_challenges", ["session_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_auth_challenges_session_id"), table_name="auth_challenges")
    op.drop_index(op.f("ix_auth_challenges_user_id"), table_name="auth_challenges")
    op.drop_index(op.f("ix_auth_challenges_challenge_id"), table_name="auth_challenges")
    op.drop_table("auth_challenges")
    
    op.drop_index(op.f("ix_auth_factor_bindings_factor_type"), table_name="auth_factor_bindings")
    op.drop_index(op.f("ix_auth_factor_bindings_user_id"), table_name="auth_factor_bindings")
    op.drop_table("auth_factor_bindings")
    
    op.drop_index(op.f("ix_sessions_is_valid"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_device_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_session_id"), table_name="sessions")
    op.drop_table("sessions")
    
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

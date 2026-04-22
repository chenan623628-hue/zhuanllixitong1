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
from sqlalchemy.dialects import sqlite

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
        sa.Column("failed_login_count", sa.Integer(), nullable=False, comment="连续登录失败次数"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True, comment="锁定时间"),
        sa.Column("unlock_at", sa.DateTime(timezone=True), nullable=True, comment="解锁时间"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True, comment="最后登录时间"),
        sa.Column("last_login_ip", sa.String(length=45), nullable=True, comment="最后登录IP"),
        sa.Column("last_password_change", sa.DateTime(timezone=True), nullable=True, comment="最后密码修改时间"),
        sa.Column("require_mfa", sa.Boolean(), nullable=False, comment="是否需要二阶段认证"),
        sa.Column("mfa_setup_complete", sa.Boolean(), nullable=False, comment="MFA设置是否完成"),
        sa.Column("role", sa.String(length=32), nullable=False, comment="角色：user/auditor/security_admin/system_admin"),
        sa.Column("display_name", sa.String(length=64), nullable=True, comment="显示名称"),
        sa.Column("avatar_url", sa.String(length=512), nullable=True, comment="头像URL"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=32), nullable=True, comment="时区"),
        sa.Column("locale", sa.String(length=16), nullable=True, comment="语言区域"),
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
        sa.Column("device_id", sa.String(length=64), nullable=True, comment="设备唯一标识"),
        sa.Column("device_name", sa.String(length=128), nullable=True, comment="设备名称"),
        sa.Column("user_agent", sa.String(length=512), nullable=True, comment="用户代理"),
        sa.Column("ip_address", sa.String(length=45), nullable=True, comment="IP地址"),
        sa.Column("location", sa.String(length=256), nullable=True, comment="地理位置"),
        sa.Column("refresh_token_jti", sa.String(length=36), nullable=False, comment="刷新令牌JTI"),
        sa.Column("refresh_token_hash", sa.String(length=256), nullable=True, comment="刷新令牌哈希"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最后使用时间"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="过期时间"),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, comment="是否已撤销"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True, comment="撤销时间"),
        sa.Column("revoked_by", sa.Integer(), nullable=True, comment="撤销者用户ID"),
        sa.Column("is_current", sa.Boolean(), nullable=False, comment="是否当前会话"),
        sa.Column("created_via", sa.String(length=32), nullable=True, comment="创建方式：password/mfa/sso"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        sa.UniqueConstraint("refresh_token_jti"),
        comment="会话表",
    )
    op.create_index(op.f("ix_sessions_session_id"), "sessions", ["session_id"], unique=True)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    
    op.create_table(
        "auth_factor_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="关联用户ID"),
        sa.Column("factor_type", sa.String(length=32), nullable=False, comment="因子类型：totp/sms/email/webauthn"),
        sa.Column("factor_name", sa.String(length=64), nullable=True, comment="自定义名称"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, comment="是否为主要因子"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, comment="是否已验证"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True, comment="验证时间"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True, comment="最后使用时间"),
        sa.Column("secret_data", sa.Text(), nullable=True, comment="加密存储的密钥数据"),
        sa.Column("public_data", sa.Text(), nullable=True, comment="公开数据（如手机号后四位）"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("priority", sa.Integer(), nullable=True, comment="优先级（数字越小优先级越高）"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        comment="认证因子绑定表",
    )
    op.create_index(op.f("ix_auth_factor_bindings_user_id"), "auth_factor_bindings", ["user_id"], unique=False)
    op.create_index("ix_auth_factor_bindings_user_type", "auth_factor_bindings", ["user_id", "factor_type"], unique=False)
    
    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("challenge_id", sa.String(length=64), nullable=False, comment="挑战唯一标识"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="关联用户ID"),
        sa.Column("factor_type", sa.String(length=32), nullable=False, comment="使用的因子类型"),
        sa.Column("factor_binding_id", sa.Integer(), nullable=True, comment="关联的因子绑定ID"),
        sa.Column("challenge_type", sa.String(length=32), nullable=False, comment="挑战类型：login_setup/verify"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="状态：pending/success/failed/expired"),
        sa.Column("code_hash", sa.String(length=256), nullable=True, comment="验证码哈希"),
        sa.Column("nonce", sa.String(length=64), nullable=True, comment="WebAuthn nonce"),
        sa.Column("attempts", sa.Integer(), nullable=False, comment="尝试次数"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, comment="最大尝试次数"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="过期时间"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="完成时间"),
        sa.Column("session_id", sa.String(length=64), nullable=True, comment="关联的会话ID（验证成功后创建）"),
        sa.Column("device_id", sa.String(length=64), nullable=True, comment="设备标识"),
        sa.ForeignKeyConstraint(["factor_binding_id"], ["auth_factor_bindings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id"),
        comment="认证挑战表",
    )
    op.create_index(op.f("ix_auth_challenges_challenge_id"), "auth_challenges", ["challenge_id"], unique=True)
    op.create_index(op.f("ix_auth_challenges_user_id"), "auth_challenges", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_auth_challenges_user_id"), table_name="auth_challenges")
    op.drop_index(op.f("ix_auth_challenges_challenge_id"), table_name="auth_challenges")
    op.drop_table("auth_challenges")
    
    op.drop_index("ix_auth_factor_bindings_user_type", table_name="auth_factor_bindings")
    op.drop_index(op.f("ix_auth_factor_bindings_user_id"), table_name="auth_factor_bindings")
    op.drop_table("auth_factor_bindings")
    
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index(op.f("ix_sessions_session_id"), table_name="sessions")
    op.drop_table("sessions")
    
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

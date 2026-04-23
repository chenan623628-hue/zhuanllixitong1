"""
专利-标准比对系统 V1.0
M03 RBAC模块 - 角色权限数据库迁移

创建角色表、权限表、菜单表、数据范围策略表及其关联表
Revision ID: 002_init_rbac_tables
Revises: 001_init_auth_tables
Create Date: 2026-04-05 10:30:00

"""
import sqlalchemy as sa
from alembic import op

revision = "002_init_rbac_tables"
down_revision = "001_init_auth_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False, comment="角色名称"),
        sa.Column("code", sa.String(length=64), nullable=False, comment="角色代码"),
        sa.Column("description", sa.String(length=256), nullable=True, comment="角色描述"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, comment="是否内置角色"),
        sa.Column("data_scope", sa.String(length=32), nullable=False, comment="数据范围"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
        comment="角色表",
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=True)
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)
    
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False, comment="权限名称"),
        sa.Column("code", sa.String(length=128), nullable=False, comment="权限码"),
        sa.Column("module", sa.String(length=64), nullable=False, comment="所属模块"),
        sa.Column("action", sa.String(length=32), nullable=False, comment="操作"),
        sa.Column("description", sa.String(length=256), nullable=True, comment="权限描述"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        comment="权限表",
    )
    op.create_index(op.f("ix_permissions_action"), "permissions", ["action"], unique=False)
    op.create_index(op.f("ix_permissions_code"), "permissions", ["code"], unique=True)
    op.create_index(op.f("ix_permissions_module"), "permissions", ["module"], unique=False)
    
    op.create_table(
        "menus",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True, comment="父菜单ID"),
        sa.Column("name", sa.String(length=64), nullable=False, comment="菜单名称"),
        sa.Column("code", sa.String(length=64), nullable=False, comment="菜单代码"),
        sa.Column("path", sa.String(length=256), nullable=True, comment="路由路径"),
        sa.Column("icon", sa.String(length=64), nullable=True, comment="菜单图标"),
        sa.Column("sort", sa.Integer(), nullable=False, comment="排序序号"),
        sa.Column("level", sa.Integer(), nullable=False, comment="菜单层级"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, comment="是否显示"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("permission_code", sa.String(length=128), nullable=True, comment="所需权限码"),
        sa.Column("component", sa.String(length=256), nullable=True, comment="前端组件路径"),
        sa.Column("meta", sa.Text(), nullable=True, comment="扩展元数据"),
        sa.ForeignKeyConstraint(["parent_id"], ["menus.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        comment="菜单表",
    )
    op.create_index(op.f("ix_menus_code"), "menus", ["code"], unique=True)
    op.create_index(op.f("ix_menus_parent_id"), "menus", ["parent_id"], unique=False)
    op.create_index(op.f("ix_menus_permission_code"), "menus", ["permission_code"], unique=False)
    
    op.create_table(
        "data_scope_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False, comment="策略名称"),
        sa.Column("code", sa.String(length=64), nullable=False, comment="策略代码"),
        sa.Column("description", sa.String(length=256), nullable=True, comment="策略描述"),
        sa.Column("scope_type", sa.String(length=32), nullable=False, comment="范围类型"),
        sa.Column("entity_type", sa.String(length=64), nullable=False, comment="实体类型"),
        sa.Column("filter_condition", sa.Text(), nullable=True, comment="过滤条件表达式"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        comment="数据范围策略表",
    )
    op.create_index(op.f("ix_data_scope_policies_code"), "data_scope_policies", ["code"], unique=True)
    op.create_index(op.f("ix_data_scope_policies_entity_type"), "data_scope_policies", ["entity_type"], unique=False)
    op.create_index(op.f("ix_data_scope_policies_scope_type"), "data_scope_policies", ["scope_type"], unique=False)
    
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role_id", sa.Integer(), nullable=False, comment="角色ID"),
        sa.Column("permission_id", sa.Integer(), nullable=False, comment="权限ID"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        comment="角色权限关联表",
    )
    op.create_index(op.f("ix_role_permissions_permission_id"), "role_permissions", ["permission_id"], unique=False)
    op.create_index(op.f("ix_role_permissions_role_id"), "role_permissions", ["role_id"], unique=False)
    
    op.create_table(
        "role_menus",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role_id", sa.Integer(), nullable=False, comment="角色ID"),
        sa.Column("menu_id", sa.Integer(), nullable=False, comment="菜单ID"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["menu_id"], ["menus.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "menu_id", name="uq_role_menu"),
        comment="角色菜单关联表",
    )
    op.create_index(op.f("ix_role_menus_menu_id"), "role_menus", ["menu_id"], unique=False)
    op.create_index(op.f("ix_role_menus_role_id"), "role_menus", ["role_id"], unique=False)
    
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="用户ID"),
        sa.Column("role_id", sa.Integer(), nullable=False, comment="角色ID"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, comment="是否主角色"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        comment="用户角色关联表",
    )
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)
    
    op.create_table(
        "role_data_scopes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role_id", sa.Integer(), nullable=False, comment="角色ID"),
        sa.Column("entity_type", sa.String(length=64), nullable=False, comment="实体类型"),
        sa.Column("data_scope_policy_id", sa.Integer(), nullable=True, comment="数据范围策略ID"),
        sa.Column("custom_dept_ids", sa.Text(), nullable=True, comment="自定义部门ID列表"),
        sa.Column("custom_user_ids", sa.Text(), nullable=True, comment="自定义用户ID列表"),
        sa.ForeignKeyConstraint(["data_scope_policy_id"], ["data_scope_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "entity_type", name="uq_role_data_scope"),
        comment="角色数据范围关联表",
    )
    op.create_index(op.f("ix_role_data_scopes_data_scope_policy_id"), "role_data_scopes", ["data_scope_policy_id"], unique=False)
    op.create_index(op.f("ix_role_data_scopes_entity_type"), "role_data_scopes", ["entity_type"], unique=False)
    op.create_index(op.f("ix_role_data_scopes_role_id"), "role_data_scopes", ["role_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_role_data_scopes_role_id"), table_name="role_data_scopes")
    op.drop_index(op.f("ix_role_data_scopes_entity_type"), table_name="role_data_scopes")
    op.drop_index(op.f("ix_role_data_scopes_data_scope_policy_id"), table_name="role_data_scopes")
    op.drop_table("role_data_scopes")
    
    op.drop_index(op.f("ix_user_roles_user_id"), table_name="user_roles")
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_table("user_roles")
    
    op.drop_index(op.f("ix_role_menus_role_id"), table_name="role_menus")
    op.drop_index(op.f("ix_role_menus_menu_id"), table_name="role_menus")
    op.drop_table("role_menus")
    
    op.drop_index(op.f("ix_role_permissions_role_id"), table_name="role_permissions")
    op.drop_index(op.f("ix_role_permissions_permission_id"), table_name="role_permissions")
    op.drop_table("role_permissions")
    
    op.drop_index(op.f("ix_data_scope_policies_scope_type"), table_name="data_scope_policies")
    op.drop_index(op.f("ix_data_scope_policies_entity_type"), table_name="data_scope_policies")
    op.drop_index(op.f("ix_data_scope_policies_code"), table_name="data_scope_policies")
    op.drop_table("data_scope_policies")
    
    op.drop_index(op.f("ix_menus_permission_code"), table_name="menus")
    op.drop_index(op.f("ix_menus_parent_id"), table_name="menus")
    op.drop_index(op.f("ix_menus_code"), table_name="menus")
    op.drop_table("menus")
    
    op.drop_index(op.f("ix_permissions_module"), table_name="permissions")
    op.drop_index(op.f("ix_permissions_code"), table_name="permissions")
    op.drop_index(op.f("ix_permissions_action"), table_name="permissions")
    op.drop_table("permissions")
    
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_index(op.f("ix_roles_code"), table_name="roles")
    op.drop_table("roles")

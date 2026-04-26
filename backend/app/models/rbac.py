"""
专利-标准比对系统 V1.0
M03 RBAC与权限域模块 - 数据模型
"""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Role(BaseModel):
    __tablename__ = "roles"
    __table_args__ = {"comment": "角色表"}

    name = Column(String(64), unique=True, nullable=False, index=True, comment="角色名称")
    code = Column(String(64), unique=True, nullable=False, index=True, comment="角色代码：system_admin/security_admin/auditor/user")
    description = Column(String(256), nullable=True, comment="角色描述")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    is_builtin = Column(Boolean, default=False, nullable=False, comment="是否内置角色（不可删除）")
    
    data_scope = Column(String(32), default="self", nullable=False, comment="数据范围：self/dept/all")
    
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    menus = relationship("RoleMenu", back_populates="role", cascade="all, delete-orphan")
    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Role id={self.id} code={self.code} name={self.name}>"


class Permission(BaseModel):
    __tablename__ = "permissions"
    __table_args__ = {"comment": "权限表"}

    name = Column(String(128), nullable=False, comment="权限名称")
    code = Column(String(128), unique=True, nullable=False, index=True, comment="权限码，如：user:create、task:view")
    module = Column(String(64), nullable=False, index=True, comment="所属模块：user/task/file/report/rule/term/audit/admin")
    action = Column(String(32), nullable=False, index=True, comment="操作：view/create/edit/delete/export/import")
    description = Column(String(256), nullable=True, comment="权限描述")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    
    roles = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Permission id={self.id} code={self.code}>"


class RolePermission(BaseModel):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        {"comment": "角色权限关联表"},
    )

    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色ID")
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True, comment="权限ID")
    
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")
    
    def __repr__(self) -> str:
        return f"<RolePermission role_id={self.role_id} permission_id={self.permission_id}>"


class Menu(BaseModel):
    __tablename__ = "menus"
    __table_args__ = {"comment": "菜单表"}

    parent_id = Column(Integer, ForeignKey("menus.id", ondelete="SET NULL"), nullable=True, index=True, comment="父菜单ID")
    name = Column(String(64), nullable=False, comment="菜单名称")
    code = Column(String(64), unique=True, nullable=False, index=True, comment="菜单代码")
    path = Column(String(256), nullable=True, comment="路由路径，如：/tasks、/admin/users")
    icon = Column(String(64), nullable=True, comment="菜单图标")
    
    sort = Column(Integer, default=0, nullable=False, comment="排序序号")
    level = Column(Integer, default=1, nullable=False, comment="菜单层级")
    
    is_visible = Column(Boolean, default=True, nullable=False, comment="是否显示在菜单中")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    
    permission_code = Column(String(128), nullable=True, index=True, comment="所需权限码")
    component = Column(String(256), nullable=True, comment="前端组件路径")
    
    meta = Column(Text, nullable=True, comment="扩展元数据（JSON）")
    
    children = relationship("Menu", backref="parent", remote_side="Menu.id")
    roles = relationship("RoleMenu", back_populates="menu", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Menu id={self.id} name={self.name} path={self.path}>"


class RoleMenu(BaseModel):
    __tablename__ = "role_menus"
    __table_args__ = (
        UniqueConstraint("role_id", "menu_id", name="uq_role_menu"),
        {"comment": "角色菜单关联表"},
    )

    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色ID")
    menu_id = Column(Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=False, index=True, comment="菜单ID")
    
    role = relationship("Role", back_populates="menus")
    menu = relationship("Menu", back_populates="roles")
    
    def __repr__(self) -> str:
        return f"<RoleMenu role_id={self.role_id} menu_id={self.menu_id}>"


class UserRole(BaseModel):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        {"comment": "用户角色关联表"},
    )

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色ID")
    
    is_primary = Column(Boolean, default=False, nullable=False, comment="是否主角色")
    
    role = relationship("Role", back_populates="users")
    
    def __repr__(self) -> str:
        return f"<UserRole user_id={self.user_id} role_id={self.role_id}>"


class DataScopePolicy(BaseModel):
    __tablename__ = "data_scope_policies"
    __table_args__ = {"comment": "数据范围策略表"}

    name = Column(String(128), nullable=False, comment="策略名称")
    code = Column(String(64), unique=True, nullable=False, index=True, comment="策略代码")
    description = Column(String(256), nullable=True, comment="策略描述")
    
    scope_type = Column(String(32), nullable=False, index=True, comment="范围类型：self/dept/custom/all")
    entity_type = Column(String(64), nullable=False, index=True, comment="实体类型：user/task/file/report")
    
    filter_condition = Column(Text, nullable=True, comment="过滤条件表达式")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    
    def __repr__(self) -> str:
        return f"<DataScopePolicy id={self.id} code={self.code}>"


class RoleDataScope(BaseModel):
    __tablename__ = "role_data_scopes"
    __table_args__ = (
        UniqueConstraint("role_id", "entity_type", name="uq_role_data_scope"),
        {"comment": "角色数据范围关联表"},
    )

    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True, comment="角色ID")
    entity_type = Column(String(64), nullable=False, index=True, comment="实体类型")
    data_scope_policy_id = Column(Integer, ForeignKey("data_scope_policies.id", ondelete="SET NULL"), nullable=True, index=True, comment="数据范围策略ID")
    
    custom_dept_ids = Column(Text, nullable=True, comment="自定义部门ID列表（JSON数组）")
    custom_user_ids = Column(Text, nullable=True, comment="自定义用户ID列表（JSON数组）")
    
    def __repr__(self) -> str:
        return f"<RoleDataScope role_id={self.role_id} entity_type={self.entity_type}>"


class BuiltinRoles:
    """
    内置角色定义（三员分离）
    """
    SYSTEM_ADMIN = {
        "code": "system_admin",
        "name": "系统管理员",
        "description": "系统配置、用户角色管理，不含审计查看权",
        "is_builtin": True,
        "data_scope": "all",
    }
    
    SECURITY_ADMIN = {
        "code": "security_admin",
        "name": "安全管理员",
        "description": "安全策略管理，不含审计查看权",
        "is_builtin": True,
        "data_scope": "all",
    }
    
    AUDITOR = {
        "code": "auditor",
        "name": "审计管理员",
        "description": "仅审计查看与导出，不含系统配置权",
        "is_builtin": True,
        "data_scope": "all",
    }
    
    USER = {
        "code": "user",
        "name": "普通用户",
        "description": "标准用户，可进行比对操作",
        "is_builtin": True,
        "data_scope": "self",
    }


class BuiltinPermissions:
    """
    内置权限定义
    """
    _permissions = [
        ("user", "view", "用户查看", "查看用户列表和详情"),
        ("user", "create", "用户创建", "创建新用户"),
        ("user", "edit", "用户编辑", "编辑用户信息"),
        ("user", "delete", "用户删除", "删除用户"),
        ("user", "assign_role", "角色分配", "分配用户角色"),
        
        ("role", "view", "角色查看", "查看角色列表和详情"),
        ("role", "create", "角色创建", "创建新角色"),
        ("role", "edit", "角色编辑", "编辑角色信息和权限"),
        ("role", "delete", "角色删除", "删除角色"),
        
        ("task", "view", "任务查看", "查看比对任务列表和详情"),
        ("task", "create", "任务创建", "创建新比对任务"),
        ("task", "edit", "任务编辑", "编辑任务配置"),
        ("task", "delete", "任务删除", "删除任务"),
        ("task", "execute", "任务执行", "执行比对任务"),
        
        ("file", "view", "文件查看", "查看上传文件列表"),
        ("file", "upload", "文件上传", "上传文件"),
        ("file", "delete", "文件删除", "删除文件"),
        ("file", "download", "文件下载", "下载文件"),
        
        ("report", "view", "报告查看", "查看报告列表和详情"),
        ("report", "create", "报告创建", "生成新报告"),
        ("report", "export", "报告导出", "导出报告"),
        ("report", "delete", "报告删除", "删除报告"),
        
        ("rule", "view", "规则模板查看", "查看规则模板列表"),
        ("rule", "create", "规则模板创建", "创建规则模板"),
        ("rule", "edit", "规则模板编辑", "编辑规则模板"),
        ("rule", "delete", "规则模板删除", "删除规则模板"),
        
        ("term", "view", "术语库查看", "查看术语库列表"),
        ("term", "create", "术语库创建", "创建术语条目"),
        ("term", "edit", "术语库编辑", "编辑术语条目"),
        ("term", "delete", "术语库删除", "删除术语条目"),
        
        ("audit", "view", "审计日志查看", "查看审计日志"),
        ("audit", "export", "审计日志导出", "导出审计日志"),
        
        ("admin", "system_config", "系统配置", "管理系统配置"),
        ("admin", "security_config", "安全配置", "管理安全策略"),
    ]
    
    @classmethod
    def get_permissions(cls):
        return [
            {
                "code": f"{module}:{action}",
                "name": name,
                "module": module,
                "action": action,
                "description": description,
            }
            for module, action, name, description in cls._permissions
        ]


class RolePermissionMatrix:
    """
    角色权限矩阵（三员分离）
    """
    _matrix = {
        "system_admin": [
            "user:view", "user:create", "user:edit", "user:delete", "user:assign_role",
            "role:view", "role:create", "role:edit", "role:delete",
            "task:view", "task:create", "task:edit", "task:delete", "task:execute",
            "file:view", "file:upload", "file:delete", "file:download",
            "report:view", "report:create", "report:export", "report:delete",
            "rule:view", "rule:create", "rule:edit", "rule:delete",
            "term:view", "term:create", "term:edit", "term:delete",
            "admin:system_config",
        ],
        "security_admin": [
            "user:view",
            "role:view",
            "task:view",
            "file:view",
            "report:view",
            "rule:view",
            "term:view",
            "admin:security_config",
        ],
        "auditor": [
            "audit:view", "audit:export",
            "task:view",
            "report:view",
        ],
        "user": [
            "task:view", "task:create", "task:edit", "task:execute",
            "file:view", "file:upload", "file:download",
            "report:view", "report:create", "report:export",
            "rule:view",
            "term:view",
        ],
    }
    
    @classmethod
    def get_role_permissions(cls, role_code: str) -> list[str]:
        return cls._matrix.get(role_code, [])
    
    @classmethod
    def get_all_matrix(cls) -> dict[str, list[str]]:
        return cls._matrix.copy()

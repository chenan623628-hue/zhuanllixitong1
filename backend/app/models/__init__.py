"""
专利-标准比对系统 V1.0
M01 工程基线模块 + M02 认证模块 + M03 RBAC模块 + M04 文件上传模块 + M05 任务管理模块 - 数据模型包
"""
from app.models.base import Base, BaseModel
from app.models.user import User
from app.models.session import Session
from app.models.auth_factor import AuthFactorBinding, AuthChallenge
from app.models.rbac import (
    Role, Permission, RolePermission,
    Menu, RoleMenu, UserRole,
    DataScopePolicy, RoleDataScope,
    BuiltinRoles, BuiltinPermissions, RolePermissionMatrix
)
from app.models.file import (
    File, UploadSecurityEvent,
    FileType, FileStatus, ScanStatus,
    SecurityEventType, AllowedFileTypes
)
from app.models.task import (
    Task, TaskEvent,
    TaskType, TaskStatus, TaskStatusTransition,
    PriorityLevel, TaskEventType, TaskStep, StateMachine
)

__all__ = [
    "Base", 
    "BaseModel", 
    "User", 
    "Session", 
    "AuthFactorBinding", 
    "AuthChallenge",
    "Role",
    "Permission",
    "RolePermission",
    "Menu",
    "RoleMenu",
    "UserRole",
    "DataScopePolicy",
    "RoleDataScope",
    "BuiltinRoles",
    "BuiltinPermissions",
    "RolePermissionMatrix",
    "File",
    "UploadSecurityEvent",
    "FileType",
    "FileStatus",
    "ScanStatus",
    "SecurityEventType",
    "AllowedFileTypes",
    "Task",
    "TaskEvent",
    "TaskType",
    "TaskStatus",
    "TaskStatusTransition",
    "PriorityLevel",
    "TaskEventType",
    "TaskStep",
    "StateMachine",
]

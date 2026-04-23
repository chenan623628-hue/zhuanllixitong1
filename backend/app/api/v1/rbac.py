"""
专利-标准比对系统 V1.0
M03 RBAC与权限域模块 - API 路由
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.schemas import ApiResponse
from app.core.responses import create_success_response
from app.core.auth import (
    get_current_user, 
    CurrentUser,
    require_system_admin,
    require_security_admin,
    require_auditor,
    require_permission,
)
from app.db import get_db
from app.services.rbac import (
    PermissionService,
    MenuService,
    RoleService,
    DataScopeService,
)
from app.models.rbac import (
    Role, 
    Permission, 
    Menu,
    RolePermission,
    UserRole,
    BuiltinRoles,
    BuiltinPermissions,
    RolePermissionMatrix,
)

router = APIRouter(prefix="/rbac", tags=["权限管理"])


class MenuItem(BaseModel):
    id: int
    name: str
    code: str
    path: str | None
    icon: str | None
    sort: int
    level: int
    permission_code: str | None
    component: str | None
    children: list["MenuItem"] = []


MenuItem.model_rebuild()


class RoleItem(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    is_active: bool
    is_builtin: bool
    data_scope: str


class PermissionItem(BaseModel):
    id: int
    name: str
    code: str
    module: str
    action: str
    description: str | None


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="角色名称")
    code: str = Field(..., min_length=1, max_length=64, description="角色代码")
    description: str | None = Field(None, max_length=256, description="角色描述")
    data_scope: str = Field(default="self", description="数据范围：self/dept/all")


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64, description="角色名称")
    description: str | None = Field(None, max_length=256, description="角色描述")
    is_active: bool | None = None
    data_scope: str | None = None


class AssignPermissionsRequest(BaseModel):
    permission_ids: list[int] = Field(..., description="权限ID列表")


class AssignRoleRequest(BaseModel):
    user_id: int = Field(..., description="用户ID")
    role_id: int = Field(..., description="角色ID")
    is_primary: bool = Field(default=False, description="是否为主角色")


@router.get("/menus/me", response_model=ApiResponse)
async def get_my_menus(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取当前用户可见的菜单树
    """
    menu_service = MenuService(db)
    menu_tree = menu_service.get_user_menu_tree(current_user.id)
    
    return create_success_response(
        data={"menus": menu_tree},
        message="获取菜单成功"
    )


@router.get("/menus/all", response_model=ApiResponse)
async def get_all_menus(
    include_invisible: bool = Query(False, description="是否包含不可见菜单"),
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    获取所有菜单（仅系统管理员）
    """
    menu_service = MenuService(db)
    menus = menu_service.get_all_menus(include_invisible=include_invisible)
    menu_tree = menu_service.build_menu_tree(menus)
    
    return create_success_response(
        data={"menus": menu_tree},
        message="获取菜单成功"
    )


@router.get("/roles", response_model=ApiResponse)
async def get_roles(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取角色列表
    """
    roles = db.query(Role).filter(Role.is_active == True).order_by(Role.id).all()
    
    result = [
        RoleItem(
            id=r.id,
            name=r.name,
            code=r.code,
            description=r.description,
            is_active=r.is_active,
            is_builtin=r.is_builtin,
            data_scope=r.data_scope,
        )
        for r in roles
    ]
    
    return create_success_response(
        data={"roles": result},
        message="获取角色列表成功"
    )


@router.get("/roles/{role_id}", response_model=ApiResponse)
async def get_role_detail(
    role_id: int,
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    获取角色详情（仅系统管理员）
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    
    if not role:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_RESOURCE_NOT_FOUND,
            message="角色不存在"
        )
    
    perm_service = PermissionService(db)
    role_perms = db.query(Permission).join(
        RolePermission, 
        RolePermission.permission_id == Permission.id
    ).filter(
        RolePermission.role_id == role_id
    ).all()
    
    return create_success_response(
        data={
            "role": RoleItem(
                id=role.id,
                name=role.name,
                code=role.code,
                description=role.description,
                is_active=role.is_active,
                is_builtin=role.is_builtin,
                data_scope=role.data_scope,
            ),
            "permissions": [
                PermissionItem(
                    id=p.id,
                    name=p.name,
                    code=p.code,
                    module=p.module,
                    action=p.action,
                    description=p.description,
                )
                for p in role_perms
            ]
        },
        message="获取角色详情成功"
    )


@router.post("/roles", response_model=ApiResponse)
async def create_role(
    data: RoleCreateRequest,
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    创建新角色（仅系统管理员）
    """
    existing = db.query(Role).filter(Role.code == data.code).first()
    if existing:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_ACTION_NOT_ALLOWED,
            message="角色代码已存在"
        )
    
    role = Role(
        name=data.name,
        code=data.code,
        description=data.description,
        data_scope=data.data_scope,
        is_active=True,
        is_builtin=False,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    
    return create_success_response(
        data={"role_id": role.id},
        message="角色创建成功"
    )


@router.put("/roles/{role_id}", response_model=ApiResponse)
async def update_role(
    role_id: int,
    data: RoleUpdateRequest,
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    更新角色（仅系统管理员）
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    
    if not role:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_RESOURCE_NOT_FOUND,
            message="角色不存在"
        )
    
    if role.is_builtin:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_ACTION_NOT_ALLOWED,
            message="内置角色不可修改"
        )
    
    if data.name:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.is_active is not None:
        role.is_active = data.is_active
    if data.data_scope:
        role.data_scope = data.data_scope
    
    db.commit()
    
    return create_success_response(
        message="角色更新成功"
    )


@router.post("/roles/{role_id}/permissions", response_model=ApiResponse)
async def assign_role_permissions(
    role_id: int,
    data: AssignPermissionsRequest,
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    为角色分配权限（仅系统管理员）
    """
    from app.models.rbac import RolePermission
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_RESOURCE_NOT_FOUND,
            message="角色不存在"
        )
    
    db.query(RolePermission).filter(
        RolePermission.role_id == role_id
    ).delete()
    
    for perm_id in data.permission_ids:
        rp = RolePermission(role_id=role_id, permission_id=perm_id)
        db.add(rp)
    
    db.commit()
    
    return create_success_response(
        message="权限分配成功"
    )


@router.get("/permissions", response_model=ApiResponse)
async def get_permissions(
    module: str | None = Query(None, description="按模块过滤"),
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    获取权限列表（仅系统管理员）
    """
    query = db.query(Permission).filter(Permission.is_active == True)
    
    if module:
        query = query.filter(Permission.module == module)
    
    permissions = query.order_by(Permission.module, Permission.id).all()
    
    result = [
        PermissionItem(
            id=p.id,
            name=p.name,
            code=p.code,
            module=p.module,
            action=p.action,
            description=p.description,
        )
        for p in permissions
    ]
    
    return create_success_response(
        data={"permissions": result},
        message="获取权限列表成功"
    )


@router.get("/permissions/me", response_model=ApiResponse)
async def get_my_permissions(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    获取当前用户的权限列表
    """
    perm_service = PermissionService(db)
    permissions = perm_service.get_user_permissions(current_user.id)
    
    return create_success_response(
        data={
            "permissions": permissions,
            "role": current_user.role,
            "is_system_admin": current_user.is_system_admin,
            "is_security_admin": current_user.is_security_admin,
            "is_auditor": current_user.is_auditor,
        },
        message="获取权限成功"
    )


@router.post("/roles/assign", response_model=ApiResponse)
async def assign_role_to_user(
    data: AssignRoleRequest,
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    为用户分配角色（仅系统管理员）
    """
    from app.models.user import User
    from app.models.rbac import UserRole
    
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_RESOURCE_NOT_FOUND,
            message="用户不存在"
        )
    
    role = db.query(Role).filter(Role.id == data.role_id).first()
    if not role:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_RESOURCE_NOT_FOUND,
            message="角色不存在"
        )
    
    role_service = RoleService(db)
    role_service.assign_role_to_user(
        user_id=data.user_id,
        role_id=data.role_id,
        is_primary=data.is_primary,
    )
    
    return create_success_response(
        message="角色分配成功"
    )


@router.delete("/roles/assign", response_model=ApiResponse)
async def remove_role_from_user(
    user_id: int = Query(..., description="用户ID"),
    role_id: int = Query(..., description="角色ID"),
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    移除用户角色（仅系统管理员）
    """
    role_service = RoleService(db)
    success = role_service.remove_role_from_user(user_id=user_id, role_id=role_id)
    
    if not success:
        from app.core.exceptions import PermissionException
        from app.core.schemas import ErrorCode
        raise PermissionException(
            code=ErrorCode.PERM_ACTION_NOT_ALLOWED,
            message="用户角色不存在"
        )
    
    return create_success_response(
        message="角色移除成功"
    )


@router.get("/roles/builtin", response_model=ApiResponse)
async def get_builtin_roles_info(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    获取内置角色说明（三员分离）
    """
    return create_success_response(
        data={
            "system_admin": {
                "code": "system_admin",
                "name": "系统管理员",
                "description": "系统配置、用户角色管理，不含审计查看权",
                "has_audit_access": False,
                "has_system_config_access": True,
                "has_security_config_access": False,
            },
            "security_admin": {
                "code": "security_admin",
                "name": "安全管理员",
                "description": "安全策略管理，不含审计查看权",
                "has_audit_access": False,
                "has_system_config_access": False,
                "has_security_config_access": True,
            },
            "auditor": {
                "code": "auditor",
                "name": "审计管理员",
                "description": "仅审计查看与导出，不含系统配置权",
                "has_audit_access": True,
                "has_system_config_access": False,
                "has_security_config_access": False,
            },
            "user": {
                "code": "user",
                "name": "普通用户",
                "description": "标准用户，可进行比对操作",
                "has_audit_access": False,
                "has_system_config_access": False,
                "has_security_config_access": False,
            },
        },
        message="获取内置角色信息成功"
    )


@router.post("/init", response_model=ApiResponse)
async def init_rbac_data(
    current_user: CurrentUser = Depends(require_system_admin()),
    db: Session = Depends(get_db),
):
    """
    初始化RBAC数据（仅系统管理员）
    初始化内置角色和权限
    """
    role_service = RoleService(db)
    role_service.init_builtin_roles()
    
    return create_success_response(
        message="RBAC数据初始化成功"
    )

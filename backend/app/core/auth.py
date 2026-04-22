"""
专利-标准比对系统 V1.0
M02 认证与会话模块 + M03 RBAC模块 - 认证与权限中间件
"""
import logging
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthException, PermissionException
from app.core.schemas import ErrorCode
from app.models.user import User
from app.services.auth.jwt_service import decode_token, get_token_subject, is_access_token
from app.services.rbac import PermissionService
from app.db import get_db

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    permissions: list[str] = []
    
    @property
    def is_system_admin(self) -> bool:
        return self.role == "system_admin"
    
    @property
    def is_security_admin(self) -> bool:
        return self.role == "security_admin"
    
    @property
    def is_auditor(self) -> bool:
        return self.role == "auditor"
    
    @property
    def is_admin(self) -> bool:
        return self.is_system_admin or self.is_security_admin
    
    @property
    def is_builtin_admin(self) -> bool:
        return self.is_system_admin
    
    def has_permission(self, permission_code: str) -> bool:
        return permission_code in self.permissions
    
    def has_any_permission(self, permission_codes: list[str]) -> bool:
        return any(p in self.permissions for p in permission_codes)
    
    def has_all_permissions(self, permission_codes: list[str]) -> bool:
        return all(p in self.permissions for p in permission_codes)


def get_token_from_header(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials:
        return credentials.credentials
    return None


def get_token_from_request(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db)
) -> CurrentUser:
    token = get_token_from_header(credentials) or get_token_from_request(request)
    
    if not token:
        raise AuthException(
            code=ErrorCode.AUTH_TOKEN_MISSING,
            message="未登录，请先登录"
        )
    
    payload = decode_token(token)
    if not payload or not is_access_token(token):
        raise AuthException(
            code=ErrorCode.AUTH_TOKEN_EXPIRED,
            message="登录已过期，请重新登录"
        )
    
    user_id = get_token_subject(token)
    if not user_id:
        raise AuthException(
            code=ErrorCode.AUTH_TOKEN_EXPIRED,
            message="登录已过期，请重新登录"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthException(
            code=ErrorCode.PERM_RESOURCE_NOT_FOUND,
            message="用户不存在"
        )
    
    if not user.is_active:
        raise AuthException(
            code=ErrorCode.AUTH_PERMISSION_DENIED,
            message="账户已被禁用"
        )
    
    if user.is_locked:
        raise AuthException(
            code=ErrorCode.AUTH_PERMISSION_DENIED,
            message="账户已被锁定"
        )
    
    perm_service = PermissionService(db)
    permissions = perm_service.get_user_permissions(user_id)
    
    return CurrentUser(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        permissions=permissions,
    )


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db)
) -> CurrentUser | None:
    try:
        return await get_current_user(request, credentials, db)
    except AuthException:
        return None
    except Exception:
        return None


def require_role(*roles: str):
    async def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise PermissionException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="权限不足"
            )
        return current_user
    return role_checker


def require_permission(permission_code: str):
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not current_user.has_permission(permission_code):
            raise PermissionException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message=f"需要权限：{permission_code}"
            )
        return current_user
    return permission_checker


def require_any_permission(*permission_codes: str):
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not current_user.has_any_permission(list(permission_codes)):
            raise PermissionException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message=f"需要以下任一权限：{', '.join(permission_codes)}"
            )
        return current_user
    return permission_checker


def require_all_permissions(*permission_codes: str):
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not current_user.has_all_permissions(list(permission_codes)):
            raise PermissionException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message=f"需要以下所有权限：{', '.join(permission_codes)}"
            )
        return current_user
    return permission_checker


def require_system_admin():
    return require_role("system_admin")


def require_security_admin():
    return require_role("security_admin")


def require_auditor():
    return require_role("auditor")


def require_admin():
    return require_role("system_admin", "security_admin")


def require_audit_access():
    async def checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> CurrentUser:
        perm_service = PermissionService(db)
        if not perm_service.has_audit_access(current_user.id):
            raise PermissionException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="仅审计管理员可访问审计相关功能"
            )
        return current_user
    return checker


def require_system_config_access():
    async def checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> CurrentUser:
        perm_service = PermissionService(db)
        if not perm_service.has_system_config_access(current_user.id):
            raise PermissionException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="仅系统管理员可访问系统配置"
            )
        return current_user
    return checker


def require_security_config_access():
    async def checker(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> CurrentUser:
        perm_service = PermissionService(db)
        if not perm_service.has_security_config_access(current_user.id):
            raise PermissionException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="仅安全管理员可访问安全配置"
            )
        return current_user
    return checker

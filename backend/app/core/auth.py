"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - 认证中间件
"""
import logging
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthException
from app.core.schemas import ErrorCode
from app.models.user import User
from app.services.auth.jwt_service import decode_token, get_token_subject, is_access_token
from app.db import get_db

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    
    @property
    def is_admin(self) -> bool:
        return self.role in ["system_admin", "security_admin"]
    
    @property
    def is_auditor(self) -> bool:
        return self.role == "auditor"


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
    
    return CurrentUser(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role
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
            raise AuthException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="权限不足"
            )
        return current_user
    return role_checker


def require_admin():
    return require_role("system_admin", "security_admin")


def require_auditor():
    return require_role("auditor", "system_admin", "security_admin")

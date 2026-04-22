"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - 认证 API 路由
"""
from typing import Any

from fastapi import APIRouter, Depends, Request, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.schemas import ApiResponse
from app.core.responses import create_success_response
from app.core.auth import get_current_user, get_current_user_optional, CurrentUser
from app.db import get_db
from app.services.auth import AuthService, SessionService

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    device_id: str | None = Field(None, description="设备 ID")
    device_name: str | None = Field(None, description="设备名称")


class ChallengeInitRequest(BaseModel):
    factor_type: str = Field(..., description="认证因子类型")


class ChallengeVerifyRequest(BaseModel):
    challenge_id: str = Field(..., description="挑战 ID")
    verification_code: str = Field(..., description="验证码")
    device_id: str | None = Field(None, description="设备 ID（用于验证上下文匹配）")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="刷新令牌")


class LogoutRequest(BaseModel):
    session_id: str | None = Field(None, description="会话 ID（可选，不传则登出当前会话）")


@router.post("/login", response_model=ApiResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(None),
    x_forwarded_for: str | None = Header(None),
):
    client_ip = x_forwarded_for or request.client.host if request.client else None
    
    auth_service = AuthService(db)
    result = auth_service.authenticate(
        username=login_data.username,
        password=login_data.password,
        device_id=login_data.device_id,
        device_name=login_data.device_name,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    
    return create_success_response(
        data=result,
        message="登录成功" if result.get("status") == "authenticated" else "需要二阶段认证"
    )


@router.get("/factors/capabilities", response_model=ApiResponse)
async def get_capabilities(
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    capabilities = auth_service.get_auth_capabilities()
    
    return create_success_response(
        data=capabilities,
        message="获取认证能力成功"
    )


@router.post("/challenge/init", response_model=ApiResponse)
async def init_challenge(
    request: Request,
    data: ChallengeInitRequest,
    db: Session = Depends(get_db),
    x_forwarded_for: str | None = Header(None),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    from app.core.exceptions import AuthException
    from app.core.schemas import ErrorCode
    
    client_ip = x_forwarded_for or request.client.host if request.client else None
    
    if not current_user:
        raise AuthException(
            code=ErrorCode.AUTH_TOKEN_MISSING,
            message="需要登录才能发起挑战"
        )
    
    auth_service = AuthService(db)
    result = auth_service.initiate_challenge(
        user_id=current_user.id,
        factor_type=data.factor_type,
        ip_address=client_ip,
    )
    
    return create_success_response(
        data=result,
        message="挑战已发起"
    )


@router.post("/challenge/verify", response_model=ApiResponse)
async def verify_challenge(
    request: Request,
    data: ChallengeVerifyRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(None),
    x_forwarded_for: str | None = Header(None),
    current_user: CurrentUser | None = Depends(get_current_user_optional),
):
    from app.core.exceptions import AuthException
    from app.core.schemas import ErrorCode
    
    client_ip = x_forwarded_for or request.client.host if request.client else None
    
    auth_service = AuthService(db)
    result = auth_service.verify_challenge(
        challenge_id=data.challenge_id,
        verification_code=data.verification_code,
        device_id=data.device_id,
        ip_address=client_ip,
        user_agent=user_agent,
        current_user_id=current_user.id if current_user else None,
    )
    
    return create_success_response(
        data=result,
        message="验证成功"
    )


@router.post("/logout", response_model=ApiResponse)
async def logout(
    data: LogoutRequest | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    auth_service = AuthService(db)
    
    if data and data.session_id:
        success = auth_service.logout(data.session_id, current_user.id)
    else:
        success = auth_service.logout_all_sessions(current_user.id)
    
    return create_success_response(
        data={"success": success},
        message="已登出"
    )


@router.post("/refresh", response_model=ApiResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    session_service = SessionService(db)
    result = session_service.refresh_access_token(data.refresh_token)
    
    if not result:
        from app.core.exceptions import AuthException
        from app.core.schemas import ErrorCode
        raise AuthException(
            code=ErrorCode.AUTH_TOKEN_EXPIRED,
            message="刷新令牌无效或已过期"
        )
    
    return create_success_response(
        data=result,
        message="令牌刷新成功"
    )


@router.get("/me", response_model=ApiResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
):
    return create_success_response(
        data={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "is_admin": current_user.is_admin,
            "is_auditor": current_user.is_auditor,
        },
        message="获取用户信息成功"
    )


@router.get("/sessions", response_model=ApiResponse)
async def get_user_sessions(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    auth_service = AuthService(db)
    sessions = auth_service.get_current_user_sessions(current_user.id)
    
    return create_success_response(
        data={"sessions": sessions},
        message="获取会话列表成功"
    )

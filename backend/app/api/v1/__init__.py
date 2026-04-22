"""
专利-标准比对系统 V1.0
M01 工程基线模块 + M02 认证模块 + M03 RBAC模块 - API 路由
"""
from app.core.schemas import ApiResponse
from app.core.responses import create_success_response
from app.api.v1.auth import router as auth_router
from app.api.v1.rbac import router as rbac_router

from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(rbac_router)


@api_router.get("/", response_model=ApiResponse)
async def api_root():
    return create_success_response(
        data={
            "version": "v1",
            "endpoints": [
                "/health",
                "/ready",
                "/auth/login",
                "/auth/factors/capabilities",
                "/auth/challenge/init",
                "/auth/challenge/verify",
                "/auth/logout",
                "/auth/refresh",
                "/auth/me",
                "/rbac/menus/me",
                "/rbac/permissions/me",
                "/rbac/roles",
            ]
        },
        message="API v1 入口"
    )

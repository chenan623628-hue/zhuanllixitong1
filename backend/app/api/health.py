"""
专利-标准比对系统 V1.0
M01 工程基线模块 - API 路由
"""
from app.core.schemas import ApiResponse
from app.core.responses import create_success_response

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/", response_model=ApiResponse)
async def api_root():
    return create_success_response(
        data={
            "version": "v1",
            "endpoints": [
                "/health",
                "/ready",
            ]
        },
        message="API v1 入口"
    )

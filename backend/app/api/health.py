"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 健康检查接口
"""
from datetime import datetime

from fastapi import APIRouter

from app.core.config import settings
from app.core.schemas import HealthResponse, ReadyResponse
from app.core.responses import create_success_response

health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@health_router.get("/ready", response_model=ReadyResponse)
async def readiness_check():
    return ReadyResponse(
        status="ready",
        version=settings.VERSION,
        checks={
            "api": True,
            "config": True,
        },
    )


@health_router.get("/health/status")
async def status_check():
    return create_success_response(
        data={
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        message="服务状态正常"
    )

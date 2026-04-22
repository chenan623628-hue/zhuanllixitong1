"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 响应辅助函数
"""
from typing import Any

from app.core.schemas import ApiResponse, ErrorMessage, ErrorCode


def create_success_response(
    data: Any = None, 
    message: str = "操作成功",
    request_id: str = ""
) -> ApiResponse:
    return ApiResponse(
        code=ErrorCode.SUCCESS,
        message=message,
        data=data,
        request_id=request_id,
    )


def create_error_response(
    code: int,
    message: str | None = None,
    data: Any = None,
    request_id: str = ""
) -> ApiResponse:
    if message is None:
        message = ErrorMessage.get(code)
    
    return ApiResponse(
        code=code,
        message=message,
        data=data,
        request_id=request_id,
    )


def create_validation_error_response(
    errors: list[dict[str, Any]],
    request_id: str = ""
) -> ApiResponse:
    return create_error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message="参数校验失败",
        data={"errors": errors},
        request_id=request_id,
    )


def create_internal_error_response(
    message: str = "服务器内部错误",
    request_id: str = ""
) -> ApiResponse:
    return create_error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message=message,
        request_id=request_id,
    )

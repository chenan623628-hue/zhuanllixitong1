"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 全局异常处理
"""
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.schemas import ErrorCode


class BusinessException(Exception):
    def __init__(
        self, 
        code: int, 
        message: str | None = None,
        data: Any = None
    ):
        self.code = code
        self.message = message or "业务异常"
        self.data = data
        super().__init__(self.message)


class AuthException(BusinessException):
    def __init__(
        self, 
        code: int = ErrorCode.AUTH_TOKEN_MISSING,
        message: str | None = None,
        data: Any = None
    ):
        super().__init__(code, message, data)


class PermissionException(BusinessException):
    def __init__(
        self, 
        code: int = ErrorCode.PERM_ACCESS_DENIED,
        message: str | None = None,
        data: Any = None
    ):
        super().__init__(code, message, data)


class FileException(BusinessException):
    def __init__(
        self, 
        code: int = ErrorCode.FILE_UPLOAD_FAILED,
        message: str | None = None,
        data: Any = None
    ):
        super().__init__(code, message, data)


class TaskException(BusinessException):
    def __init__(
        self, 
        code: int = ErrorCode.TASK_CREATE_FAILED,
        message: str | None = None,
        data: Any = None
    ):
        super().__init__(code, message, data)


class EngineException(BusinessException):
    def __init__(
        self, 
        code: int = ErrorCode.ENGINE_COMPARE_FAILED,
        message: str | None = None,
        data: Any = None
    ):
        super().__init__(code, message, data)


def get_trace_id() -> str:
    try:
        from app.core.tracing import get_current_trace_id
        return get_current_trace_id()
    except Exception:
        return "unknown"


def create_error_response(
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
        "request_id": get_trace_id(),
    }


def add_exception_handlers(app: FastAPI) -> None:
    logger = logging.getLogger(__name__)

    @app.exception_handler(BusinessException)
    async def business_exception_handler(
        request: Request, exc: BusinessException
    ) -> JSONResponse:
        logger.warning(f"业务异常: [{exc.code}] {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=create_error_response(exc.code, exc.message, exc.data),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        logger.warning(f"HTTP 异常: [{exc.status_code}] {exc.detail}")
        
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            code = ErrorCode.AUTH_TOKEN_MISSING
            message = str(exc.detail) if exc.detail else "未授权访问"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            code = ErrorCode.PERM_ACCESS_DENIED
            message = str(exc.detail) if exc.detail else "权限不足"
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            code = ErrorCode.PERM_RESOURCE_NOT_FOUND
            message = str(exc.detail) if exc.detail else "资源不存在"
        else:
            code = ErrorCode.INTERNAL_ERROR
            message = str(exc.detail) if exc.detail else "服务器内部错误"
        
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(code, message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            errors.append({
                "location": error.get("loc", []),
                "field": ".".join(str(x) for x in error.get("loc", []) if x != "body"),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })
        
        logger.warning(f"参数校验失败: {errors}")
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=create_error_response(
                ErrorCode.VALIDATION_ERROR,
                "参数校验失败",
                {"errors": errors},
            ),
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            errors.append({
                "location": error.get("loc", []),
                "field": ".".join(str(x) for x in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })
        
        logger.warning(f"数据校验失败: {errors}")
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=create_error_response(
                ErrorCode.VALIDATION_ERROR,
                "数据校验失败",
                {"errors": errors},
            ),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(f"未捕获异常: {str(exc)}", exc_info=True)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                ErrorCode.INTERNAL_ERROR,
                "服务器内部错误",
            ),
        )

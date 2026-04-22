"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 请求追踪
"""
import time
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
_request_start_var: ContextVar[float] = ContextVar("request_start", default=0.0)


def get_current_trace_id() -> str:
    return _trace_id_var.get() or "unknown"


def set_current_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def generate_trace_id() -> str:
    return f"trace-{uuid.uuid4().hex[:12]}"


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or generate_trace_id()
        
        token = _trace_id_var.set(trace_id)
        start_time = time.time()
        _request_start_var.set(start_time)
        
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[{trace_id}] 请求开始: {request.method} {request.url.path}"
            )
            
            response = await call_next(request)
            
            response.headers["X-Trace-Id"] = trace_id
            
            duration = time.time() - start_time
            logger.info(
                f"[{trace_id}] 请求完成: {response.status_code} ({duration*1000:.2f}ms)"
            )
            
            return response
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[{trace_id}] 请求异常: {str(e)}", exc_info=True)
            raise
        finally:
            _trace_id_var.reset(token)


def add_tracing_middleware(app: Any) -> None:
    app.add_middleware(TracingMiddleware)

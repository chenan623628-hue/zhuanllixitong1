"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 日志系统
"""
import logging
import sys
from typing import Any

from app.core.config import settings
from app.core.tracing import get_current_trace_id


class TraceIdFilter(logging.Filter):
    def filter(self, record: Any) -> bool:
        record.trace_id = get_current_trace_id()
        return True


def setup_logging() -> None:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.addFilter(TraceIdFilter())
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(trace_id)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.setLevel(log_level)
        for handler in uvicorn_logger.handlers[:]:
            uvicorn_logger.removeHandler(handler)
        uvicorn_logger.addHandler(console_handler)
        uvicorn_logger.propagate = False
    
    logging.info(f"日志系统初始化完成，日志级别: {settings.LOG_LEVEL}")


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or __name__)

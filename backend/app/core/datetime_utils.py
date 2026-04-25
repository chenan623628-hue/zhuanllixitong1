"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 时间工具模块

统一处理 timezone-aware UTC 时间，消除 datetime.utcnow() 弃用警告
"""
from datetime import datetime, timezone
from typing import Callable


def utcnow() -> datetime:
    """
    返回当前 timezone-aware UTC 时间
    
    替代已弃用的 datetime.utcnow()
    
    使用示例：
        from app.core.datetime_utils import utcnow
        now = utcnow()  # 返回 timezone-aware datetime
    """
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """
    返回当前 naive UTC 时间（移除时区信息）
    
    用于与存储为 naive datetime 的数据库字段兼容
    
    警告：优先使用 utcnow()，仅在确有必要时使用此函数
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc(dt: datetime) -> datetime:
    """
    将 datetime 转换为 timezone-aware UTC 时间
    
    Args:
        dt: 输入的 datetime（可以是 naive 或 timezone-aware）
    
    Returns:
        timezone-aware UTC datetime
        
    注意：
        - 如果 dt 是 naive，假设其为 UTC 时间
        - 如果 dt 是 timezone-aware，转换为 UTC
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    else:
        return dt.astimezone(timezone.utc)


def get_default_func() -> Callable[[], datetime]:
    """
    返回可用于 SQLAlchemy Column default 的函数
    
    使用示例：
        from app.core.datetime_utils import get_default_func
        created_at = Column(DateTime, default=get_default_func(), ...)
    """
    return utcnow


def get_onupdate_func() -> Callable[[], datetime]:
    """
    返回可用于 SQLAlchemy Column onupdate 的函数
    """
    return utcnow

"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 时间工具模块

统一处理 UTC 时间，消除 datetime.utcnow() 弃用警告

注意：当前数据库使用 DateTime 列（无时区），因此所有数据库操作
都使用 naive UTC 时间。如果未来升级到时区感知列，可以切换到
timezone-aware 版本。
"""
from datetime import datetime, timezone
from typing import Callable


def utcnow() -> datetime:
    """
    返回当前 naive UTC 时间（无时区信息）
    
    替代已弃用的 datetime.utcnow()
    
    使用示例：
        from app.core.datetime_utils import utcnow
        now = utcnow()  # 返回 naive datetime
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcnow_aware() -> datetime:
    """
    返回当前 timezone-aware UTC 时间
    
    警告：仅用于需要时区信息的场景，不要直接与数据库列比较
    """
    return datetime.now(timezone.utc)


def to_naive_utc(dt: datetime) -> datetime:
    """
    将 datetime 转换为 naive UTC 时间
    
    Args:
        dt: 输入的 datetime（可以是 naive 或 timezone-aware）
    
    Returns:
        naive UTC datetime
        
    注意：
        - 如果 dt 是 naive，假设其为 UTC 时间
        - 如果 dt 是 timezone-aware，转换为 UTC 后移除时区信息
    """
    if dt.tzinfo is None:
        return dt
    else:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)


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

"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 数据库基础模型
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


def _utcnow() -> datetime:
    """
    返回当前 timezone-aware UTC 时间
    替代已弃用的 datetime.utcnow()
    """
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime, default=_utcnow, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False, comment="更新时间")


class BaseModel(Base, TimestampMixin):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")

    def to_dict(self) -> dict:
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"

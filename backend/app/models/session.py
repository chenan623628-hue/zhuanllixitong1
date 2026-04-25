"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - 会话数据模型
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text
from app.models.base import BaseModel


def _utcnow() -> datetime:
    """返回 naive UTC 时间"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Session(BaseModel):
    __tablename__ = "sessions"
    __table_args__ = {"comment": "会话表"}

    user_id = Column(Integer, nullable=False, index=True, comment="用户 ID")
    
    session_id = Column(String(64), unique=True, nullable=False, index=True, comment="会话 ID")
    refresh_token_hash = Column(String(256), nullable=False, comment="Refresh Token 哈希")
    
    access_token_expires_at = Column(DateTime, nullable=False, comment="Access Token 过期时间")
    refresh_token_expires_at = Column(DateTime, nullable=False, comment="Refresh Token 过期时间")
    
    device_id = Column(String(64), nullable=True, index=True, comment="设备 ID")
    device_name = Column(String(128), nullable=True, comment="设备名称")
    device_type = Column(String(32), nullable=True, comment="设备类型：web/mobile/desktop")
    device_os = Column(String(64), nullable=True, comment="操作系统")
    device_browser = Column(String(64), nullable=True, comment="浏览器")
    
    ip_address = Column(String(64), nullable=True, comment="登录 IP 地址")
    location = Column(String(128), nullable=True, comment="登录位置")
    user_agent = Column(Text, nullable=True, comment="完整 User-Agent")
    
    is_valid = Column(Boolean, default=True, nullable=False, index=True, comment="会话是否有效")
    invalidated_at = Column(DateTime, nullable=True, comment="失效时间")
    invalidated_reason = Column(String(128), nullable=True, comment="失效原因：logout/token_revoked/admin_action")
    
    last_activity_at = Column(DateTime, default=_utcnow, nullable=False, comment="最后活跃时间")
    
    def __repr__(self) -> str:
        return f"<Session id={self.id} user_id={self.user_id} valid={self.is_valid}>"

"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - 用户数据模型
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    username = Column(String(64), unique=True, nullable=False, index=True, comment="用户名")
    email = Column(String(128), unique=True, nullable=True, index=True, comment="邮箱")
    phone = Column(String(32), unique=True, nullable=True, index=True, comment="手机号")
    password_hash = Column(String(256), nullable=False, comment="密码哈希")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="是否激活")
    is_locked = Column(Boolean, default=False, nullable=False, comment="是否锁定")
    locked_at = Column(DateTime, nullable=True, comment="锁定时间")
    failed_login_count = Column(Integer, default=0, nullable=False, comment="连续登录失败次数")
    
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    last_login_ip = Column(String(64), nullable=True, comment="最后登录 IP")
    last_login_device = Column(String(256), nullable=True, comment="最后登录设备")
    
    require_mfa = Column(Boolean, default=False, nullable=False, comment="是否需要二阶段认证")
    mfa_enabled_factors = Column(Text, nullable=True, comment="已启用的认证因子（JSON 数组）")
    
    role = Column(String(32), default="user", nullable=False, comment="角色：user/auditor/security_admin/system_admin")
    
    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username}>"

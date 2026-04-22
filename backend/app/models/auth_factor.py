"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - 认证因子绑定数据模型
"""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text
from app.models.base import BaseModel


class AuthFactorBinding(BaseModel):
    __tablename__ = "auth_factor_bindings"
    __table_args__ = {"comment": "认证因子绑定表"}

    user_id = Column(Integer, nullable=False, index=True, comment="用户 ID")
    
    factor_type = Column(String(32), nullable=False, index=True, comment="认证因子类型：password/totp/sms/email/ukey")
    factor_name = Column(String(64), nullable=True, comment="认证因子名称（用户自定义）")
    
    is_verified = Column(Boolean, default=False, nullable=False, comment="是否已验证")
    is_primary = Column(Boolean, default=False, nullable=False, comment="是否为主认证因子")
    
    config_data = Column(Text, nullable=True, comment="配置数据（JSON 格式，如 TOTP 的密钥等）")
    metadata = Column(Text, nullable=True, comment="元数据（JSON 格式）")
    
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    last_verified_at = Column(DateTime, nullable=True, comment="最后验证成功时间")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    
    def __repr__(self) -> str:
        return f"<AuthFactorBinding id={self.id} user_id={self.user_id} type={self.factor_type}>"


class AuthChallenge(BaseModel):
    __tablename__ = "auth_challenges"
    __table_args__ = {"comment": "认证挑战记录表"}

    user_id = Column(Integer, nullable=False, index=True, comment="用户 ID")
    session_id = Column(String(64), nullable=True, index=True, comment="会话 ID")
    
    challenge_id = Column(String(64), unique=True, nullable=False, index=True, comment="挑战 ID")
    challenge_type = Column(String(32), nullable=False, comment="挑战类型：totp/sms/email/ukey")
    
    challenge_data = Column(Text, nullable=True, comment="挑战数据（JSON 格式，如验证码、提示等）")
    
    status = Column(String(32), default="pending", nullable=False, comment="状态：pending/success/failed/expired")
    attempts = Column(Integer, default=0, nullable=False, comment="尝试次数")
    max_attempts = Column(Integer, default=3, nullable=False, comment="最大尝试次数")
    
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    
    device_id = Column(String(64), nullable=True, comment="设备 ID")
    ip_address = Column(String(64), nullable=True, comment="IP 地址")
    
    def __repr__(self) -> str:
        return f"<AuthChallenge id={self.id} user_id={self.user_id} type={self.challenge_type} status={self.status}>"


class AuthFactorCapability:
    """
    认证因子能力枚举（不存数据库，用于能力目录接口）
    """
    FACTOR_TYPES = {
        "password": {
            "name": "密码登录",
            "description": "用户名密码认证",
            "supported": True,
            "required_config": ["username", "password"]
        },
        "totp": {
            "name": "TOTP 动态令牌",
            "description": "基于时间的一次性密码",
            "supported": True,
            "required_config": ["secret"]
        },
        "sms": {
            "name": "短信验证码",
            "description": "手机短信验证码",
            "supported": True,
            "required_config": ["phone"]
        },
        "email": {
            "name": "邮箱验证码",
            "description": "邮箱验证码",
            "supported": True,
            "required_config": ["email"]
        },
        "ukey": {
            "name": "UKey 硬件密钥",
            "description": "USB Key 硬件认证",
            "supported": False,
            "required_config": []
        }
    }

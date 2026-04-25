"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - JWT 服务
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt as jose_jwt

from app.core.config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: int | str, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = _utcnow() + expires_delta
    else:
        expire = _utcnow() + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
        "iat": _utcnow()
    }
    
    encoded_jwt = jose_jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(subject: int | str, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = _utcnow() + expires_delta
    else:
        expire = _utcnow() + timedelta(
            minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
        "iat": _utcnow()
    }
    
    encoded_jwt = jose_jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jose_jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jose_jwt.ExpiredSignatureError:
        return None
    except JWTError:
        return None


def get_token_subject(token: str) -> int | None:
    payload = decode_token(token)
    if payload and "sub" in payload:
        try:
            return int(payload["sub"])
        except (ValueError, TypeError):
            return None
    return None


def is_access_token(token: str) -> bool:
    payload = decode_token(token)
    return payload is not None and payload.get("type") == "access"


def is_refresh_token(token: str) -> bool:
    payload = decode_token(token)
    return payload is not None and payload.get("type") == "refresh"


def get_token_expiry(token: str) -> datetime | None:
    payload = decode_token(token)
    if payload and "exp" in payload:
        try:
            return datetime.fromtimestamp(payload["exp"])
        except (ValueError, TypeError):
            return None
    return None

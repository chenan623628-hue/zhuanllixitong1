"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - 会话服务
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.session import Session as SessionModel
from app.models.user import User
from app.services.auth.jwt_service import create_access_token, create_refresh_token, decode_token, get_token_subject
from app.services.auth.password import generate_session_id, hash_token, verify_token_hash
from app.core.config import settings

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(
        self,
        user: User,
        device_id: str | None = None,
        device_name: str | None = None,
        device_type: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES)
        
        access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)
        refresh_token_raw = create_refresh_token(subject=user.id, expires_delta=refresh_token_expires)
        
        refresh_token_hash = hash_token(refresh_token_raw)
        session_id = generate_session_id()
        
        access_expires_at = _utcnow() + access_token_expires
        refresh_expires_at = _utcnow() + refresh_token_expires
        
        session = SessionModel(
            user_id=user.id,
            session_id=session_id,
            refresh_token_hash=refresh_token_hash,
            access_token_expires_at=access_expires_at,
            refresh_token_expires_at=refresh_expires_at,
            device_id=device_id or str(uuid4()),
            device_name=device_name,
            device_type=device_type or "web",
            ip_address=ip_address,
            user_agent=user_agent,
            is_valid=True,
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"Created session for user {user.id} (session_id: {session_id})")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token_raw,
            "session_id": session_id,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    
    def get_session_by_id(self, session_id: str) -> SessionModel | None:
        return self.db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()
    
    def get_valid_sessions_by_user_id(self, user_id: int) -> list[SessionModel]:
        return self.db.query(SessionModel).filter(
            SessionModel.user_id == user_id,
            SessionModel.is_valid == True,
            SessionModel.refresh_token_expires_at > _utcnow()
        ).all()
    
    def invalidate_session(self, session_id: str, reason: str = "logout") -> bool:
        session = self.get_session_by_id(session_id)
        if not session:
            return False
        
        session.is_valid = False
        session.invalidated_at = _utcnow()
        session.invalidated_reason = reason
        
        self.db.commit()
        logger.info(f"Invalidated session {session_id} for user {session.user_id}, reason: {reason}")
        return True
    
    def invalidate_all_user_sessions(self, user_id: int, reason: str = "admin_action") -> int:
        sessions = self.get_valid_sessions_by_user_id(user_id)
        count = 0
        for session in sessions:
            session.is_valid = False
            session.invalidated_at = _utcnow()
            session.invalidated_reason = reason
            count += 1
        
        self.db.commit()
        logger.info(f"Invalidated {count} sessions for user {user_id}, reason: {reason}")
        return count
    
    def refresh_access_token(self, refresh_token: str) -> dict[str, Any] | None:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = get_token_subject(refresh_token)
        if not user_id:
            return None
        
        refresh_token_hash = hash_token(refresh_token)
        session = self.db.query(SessionModel).filter(
            SessionModel.user_id == user_id,
            SessionModel.refresh_token_hash == refresh_token_hash,
            SessionModel.is_valid == True,
            SessionModel.refresh_token_expires_at > _utcnow()
        ).first()
        
        if not session:
            return None
        
        access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(subject=user_id, expires_delta=access_token_expires)
        
        session.last_activity_at = _utcnow()
        self.db.commit()
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    
    def update_session_activity(self, session_id: str) -> bool:
        session = self.get_session_by_id(session_id)
        if not session:
            return False
        
        session.last_activity_at = _utcnow()
        self.db.commit()
        return True
    
    def cleanup_expired_sessions(self) -> int:
        cutoff = _utcnow() - timedelta(days=30)
        expired = self.db.query(SessionModel).filter(
            SessionModel.refresh_token_expires_at < cutoff
        ).all()
        
        count = len(expired)
        for session in expired:
            self.db.delete(session)
        
        self.db.commit()
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
        
        return count

"""
专利-标准比对系统 V1.0
M02 认证与会话模块 - 密码安全服务
"""
import hashlib
import secrets
import string
from datetime import datetime

import bcrypt


def generate_salt(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def generate_random_token(length: int = 32) -> str:
    return secrets.token_hex(length)


def generate_session_id() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, expected_hash: str) -> bool:
    actual_hash = hash_token(token)
    return secrets.compare_digest(actual_hash, expected_hash)

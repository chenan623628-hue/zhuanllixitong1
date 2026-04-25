"""
专利-标准比对系统 V1.0
数据库初始化脚本

创建数据库表并插入默认管理员用户
"""
import sys
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.models.base import Base

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_EMAIL = "admin@example.com"


def safe_print(*args, **kwargs):
    """
    安全打印函数，避免Windows GBK控制台Unicode编码错误
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or "utf-8"
            new_args = []
            for arg in args:
                if isinstance(arg, str):
                    new_args.append(arg.encode(encoding, errors="replace").decode(encoding))
                else:
                    new_args.append(arg)
            print(*new_args, **kwargs)
        except:
            pass


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def init_database():
    safe_print("=" * 60)
    safe_print("专利-标准比对系统 - 数据库初始化")
    safe_print("=" * 60)
    
    db_url = settings.DATABASE_URL
    connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}
    
    engine = create_engine(
        db_url,
        echo=settings.DEBUG,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    
    safe_print(f"\n数据库连接: {db_url}")
    safe_print("\n[1/4] 创建数据库表...")
    
    Base.metadata.create_all(bind=engine)
    
    safe_print("[OK] 表创建完成")
    
    safe_print("\n[2/4] 检查默认管理员用户...")
    
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": DEFAULT_ADMIN_USERNAME}
        )
        existing_user = result.fetchone()
    
    if existing_user:
        safe_print(f"[OK] 管理员用户 '{DEFAULT_ADMIN_USERNAME}' 已存在")
    else:
        safe_print("[3/4] 创建默认管理员用户...")
        
        password_hash = get_password_hash(DEFAULT_ADMIN_PASSWORD)
        now = datetime.now(timezone.utc)
        
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO users (
                    username, email, password_hash, is_active, is_locked,
                    failed_login_count, require_mfa, role,
                    created_at, updated_at
                ) VALUES (
                    :username, :email, :password_hash, :is_active, :is_locked,
                    :failed_login_count, :require_mfa, :role,
                    :created_at, :updated_at
                )
                """),
                {
                    "username": DEFAULT_ADMIN_USERNAME,
                    "email": DEFAULT_ADMIN_EMAIL,
                    "password_hash": password_hash,
                    "is_active": True,
                    "is_locked": False,
                    "failed_login_count": 0,
                    "require_mfa": False,
                    "role": "system_admin",
                    "created_at": now,
                    "updated_at": now,
                }
            )
        
        safe_print(f"[OK] 管理员用户 '{DEFAULT_ADMIN_USERNAME}' 创建成功")
    
    safe_print("\n[4/4] 数据库初始化完成")
    safe_print("=" * 60)
    safe_print("\n默认管理员账号:")
    safe_print(f"  用户名: {DEFAULT_ADMIN_USERNAME}")
    safe_print(f"  密码: {DEFAULT_ADMIN_PASSWORD}")
    safe_print("\n[WARNING] 生产环境请立即修改默认密码！")
    safe_print("\n" + "=" * 60)
    
    engine.dispose()


if __name__ == "__main__":
    init_database()

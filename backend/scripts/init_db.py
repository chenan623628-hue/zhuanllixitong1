"""
专利-标准比对系统 V1.0
数据库初始化脚本

创建数据库表并插入默认管理员用户
"""
import asyncio
from datetime import datetime, timezone
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from app.core.config import settings
from app.models.base import Base

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_EMAIL = "admin@example.com"


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def init_database():
    print("=" * 60)
    print("专利-标准比对系统 - 数据库初始化")
    print("=" * 60)
    
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )
    
    print(f"\n数据库连接: {settings.DATABASE_URL}")
    print("\n[1/4] 创建数据库表...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✓ 表创建完成")
    
    print("\n[2/4] 检查默认管理员用户...")
    
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": DEFAULT_ADMIN_USERNAME}
        )
        existing_user = result.fetchone()
    
    if existing_user:
        print(f"✓ 管理员用户 '{DEFAULT_ADMIN_USERNAME}' 已存在")
    else:
        print("[3/4] 创建默认管理员用户...")
        
        password_hash = get_password_hash(DEFAULT_ADMIN_PASSWORD)
        now = datetime.now(timezone.utc)
        
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                INSERT INTO users (
                    username, email, password_hash, is_active, is_locked,
                    failed_login_count, require_mfa, mfa_setup_complete,
                    role, display_name, created_at, updated_at, timezone, locale
                ) VALUES (
                    :username, :email, :password_hash, :is_active, :is_locked,
                    :failed_login_count, :require_mfa, :mfa_setup_complete,
                    :role, :display_name, :created_at, :updated_at, :timezone, :locale
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
                    "mfa_setup_complete": False,
                    "role": "system_admin",
                    "display_name": "系统管理员",
                    "created_at": now,
                    "updated_at": now,
                    "timezone": "Asia/Shanghai",
                    "locale": "zh-CN",
                }
            )
        
        print(f"✓ 管理员用户 '{DEFAULT_ADMIN_USERNAME}' 创建成功")
    
    print("\n[4/4] 数据库初始化完成")
    print("=" * 60)
    print("\n默认管理员账号:")
    print(f"  用户名: {DEFAULT_ADMIN_USERNAME}")
    print(f"  密码: {DEFAULT_ADMIN_PASSWORD}")
    print("\n⚠️  生产环境请立即修改默认密码！")
    print("\n=" * 60)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())

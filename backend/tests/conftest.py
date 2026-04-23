"""
pytest 测试配置

使用内存数据库进行RBAC服务层测试
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def test_db():
    """
    测试数据库 fixture
    
    使用 SQLite 内存数据库，每个测试函数独立隔离
    """
    from app.models.base import Base
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_roles(test_db):
    """
    创建测试用的角色数据
    """
    from app.models.rbac import Role
    
    roles = [
        Role(
            id=1,
            code="system_admin",
            name="系统管理员",
            description="系统管理员角色",
            is_builtin=True,
            is_active=True,
            data_scope="all",
        ),
        Role(
            id=2,
            code="security_admin",
            name="安全管理员",
            description="安全管理员角色",
            is_builtin=True,
            is_active=True,
            data_scope="all",
        ),
        Role(
            id=3,
            code="auditor",
            name="审计管理员",
            description="审计管理员角色",
            is_builtin=True,
            is_active=True,
            data_scope="self",
        ),
        Role(
            id=4,
            code="user",
            name="普通用户",
            description="普通用户角色",
            is_builtin=True,
            is_active=True,
            data_scope="self",
        ),
    ]
    
    for role in roles:
        test_db.add(role)
    test_db.commit()
    
    yield roles


@pytest.fixture(scope="function")
def test_permissions(test_db):
    """
    创建测试用的权限数据
    """
    from app.models.rbac import Permission
    
    permissions = [
        Permission(
            id=1,
            code="admin:system_config",
            name="系统配置",
            module="admin",
            action="config",
            is_active=True,
        ),
        Permission(
            id=2,
            code="task:view",
            name="查看任务",
            module="task",
            action="view",
            is_active=True,
        ),
        Permission(
            id=3,
            code="audit:view",
            name="查看审计日志",
            module="audit",
            action="view",
            is_active=True,
        ),
    ]
    
    for perm in permissions:
        test_db.add(perm)
    test_db.commit()
    
    yield permissions


@pytest.fixture(scope="function")
def test_menus(test_db):
    """
    创建测试用的菜单数据
    """
    from app.models.rbac import Menu
    
    menus = [
        Menu(
            id=1,
            code="admin",
            name="系统管理",
            path="/admin",
            is_active=True,
            is_visible=True,
            level=1,
            sort=1,
        ),
        Menu(
            id=2,
            code="task",
            name="任务管理",
            path="/tasks",
            is_active=True,
            is_visible=True,
            level=1,
            sort=2,
        ),
        Menu(
            id=3,
            code="audit",
            name="审计日志",
            path="/audit",
            is_active=True,
            is_visible=True,
            level=1,
            sort=3,
        ),
    ]
    
    for menu in menus:
        test_db.add(menu)
    test_db.commit()
    
    yield menus


@pytest.fixture(scope="function")
def test_user_roles(test_db, test_roles):
    """
    为测试用户创建角色绑定
    
    返回: {user_id: [UserRole记录]}
    """
    from app.models.rbac import UserRole
    
    user_roles = [
        UserRole(
            id=1,
            user_id=1,
            role_id=1,
            is_primary=True,
        ),
        UserRole(
            id=2,
            user_id=1,
            role_id=3,
            is_primary=False,
        ),
        UserRole(
            id=3,
            user_id=2,
            role_id=4,
            is_primary=True,
        ),
    ]
    
    for ur in user_roles:
        test_db.add(ur)
    test_db.commit()
    
    yield user_roles


@pytest.fixture(scope="function")
def test_role_permissions(test_db, test_roles, test_permissions):
    """
    创建角色-权限关联
    """
    from app.models.rbac import RolePermission
    
    role_perms = [
        RolePermission(id=1, role_id=1, permission_id=1),
        RolePermission(id=2, role_id=1, permission_id=2),
        RolePermission(id=3, role_id=3, permission_id=3),
        RolePermission(id=4, role_id=4, permission_id=2),
    ]
    
    for rp in role_perms:
        test_db.add(rp)
    test_db.commit()
    
    yield role_perms


@pytest.fixture(scope="function")
def test_role_menus(test_db, test_roles, test_menus):
    """
    创建角色-菜单关联
    """
    from app.models.rbac import RoleMenu
    
    role_menus = [
        RoleMenu(id=1, role_id=1, menu_id=1),
        RoleMenu(id=2, role_id=1, menu_id=2),
        RoleMenu(id=3, role_id=3, menu_id=3),
        RoleMenu(id=4, role_id=4, menu_id=2),
    ]
    
    for rm in role_menus:
        test_db.add(rm)
    test_db.commit()
    
    yield role_menus

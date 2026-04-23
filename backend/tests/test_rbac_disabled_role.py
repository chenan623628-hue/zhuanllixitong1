import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestRole:
    def __init__(self, id, code, name, is_active=True, data_scope="self", is_builtin=False):
        self.id = id
        self.code = code
        self.name = name
        self.is_active = is_active
        self.data_scope = data_scope
        self.is_builtin = is_builtin


class TestPermission:
    def __init__(self, id, code, name, module, is_active=True):
        self.id = id
        self.code = code
        self.name = name
        self.module = module
        self.is_active = is_active


class TestMenu:
    def __init__(self, id, code, name, path, is_active=True, is_visible=True, permission_code=None, parent_id=None):
        self.id = id
        self.code = code
        self.name = name
        self.path = path
        self.is_active = is_active
        self.is_visible = is_visible
        self.permission_code = permission_code
        self.parent_id = parent_id
        self.sort = id
        self.level = 1
        self.icon = None
        self.component = None


class TestUserRole:
    def __init__(self, user_id, role_id, is_primary=False):
        self.user_id = user_id
        self.role_id = role_id
        self.is_primary = is_primary


class TestRolePermission:
    def __init__(self, role_id, permission_id):
        self.role_id = role_id
        self.permission_id = permission_id


class TestRoleMenu:
    def __init__(self, role_id, menu_id):
        self.role_id = role_id
        self.menu_id = menu_id


class MockQuery:
    def __init__(self, results=None):
        self._results = results or []
        self._filters = []
    
    def filter(self, *args, **kwargs):
        self._filters.append((args, kwargs))
        return self
    
    def join(self, *args, **kwargs):
        return self
    
    def all(self):
        return self._results
    
    def first(self):
        return self._results[0] if self._results else None
    
    def update(self, values, synchronize_session=False):
        return len(self._results)
    
    def delete(self, synchronize_session=False):
        count = len(self._results)
        self._results = []
        return count


class MockSession:
    def __init__(self):
        self._roles = {}
        self._permissions = {}
        self._menus = {}
        self._user_roles = []
        self._role_permissions = []
        self._role_menus = []
        self._committed = []
    
    def query(self, model_class):
        mock_query = MockQuery()
        
        if hasattr(model_class, '__name__'):
            model_name = model_class.__name__
        else:
            model_name = model_class
        
        if model_name == 'Role':
            mock_query._results = [r for r in self._roles.values()]
        elif model_name == 'Permission':
            mock_query._results = [p for p in self._permissions.values()]
        elif model_name == 'Menu':
            mock_query._results = [m for m in self._menus.values()]
        elif model_name == 'UserRole':
            mock_query._results = self._user_roles.copy()
        elif model_name == 'RolePermission':
            mock_query._results = self._role_permissions.copy()
        elif model_name == 'RoleMenu':
            mock_query._results = self._role_menus.copy()
        
        return mock_query
    
    def add(self, instance):
        pass
    
    def commit(self):
        self._committed.append(True)
    
    def delete(self, instance):
        pass


class MockRole:
    def __init__(self, id, code, is_active=True, data_scope="self"):
        self.id = id
        self.code = code
        self.is_active = is_active
        self.data_scope = data_scope
        self.name = f"Role_{code}"


class MockPermission:
    def __init__(self, id, code, is_active=True):
        self.id = id
        self.code = code
        self.is_active = is_active


class TestRbacServiceUnit:
    """
    RBAC服务层单元测试 - 验证角色禁用过滤逻辑
    
    测试目标：
    - 验证禁用角色后，权限不再下发
    - 验证禁用角色后，菜单不再显示
    - 验证禁用角色后，数据范围不再生效
    """
    
    def setup_method(self):
        from app.models.rbac import Role, Permission, Menu, UserRole, RolePermission, RoleMenu
        
        self.role_admin = MockRole(id=1, code="system_admin", is_active=True, data_scope="all")
        self.role_user = MockRole(id=2, code="user", is_active=True, data_scope="self")
        self.role_auditor = MockRole(id=3, code="auditor", is_active=True, data_scope="self")
        
        self.perm_admin = MockPermission(id=1, code="admin:system_config", is_active=True)
        self.perm_user = MockPermission(id=2, code="task:view", is_active=True)
        self.perm_audit = MockPermission(id=3, code="audit:view", is_active=True)
        
        self.menu_admin = TestMenu(id=1, code="admin", name="系统管理", path="/admin", is_active=True)
        self.menu_task = TestMenu(id=2, code="task", name="任务管理", path="/tasks", is_active=True)
        self.menu_audit = TestMenu(id=3, code="audit", name="审计日志", path="/audit", is_active=True)
    
    def test_get_user_roles_filters_inactive_roles(self):
        """
        测试：get_user_roles 应该过滤掉禁用的角色
        
        预期：
        - 用户绑定启用的角色时，返回该角色
        - 用户绑定禁用的角色时，不返回该角色
        """
        from app.services.rbac import PermissionService
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
        ]
        
        service = PermissionService(mock_db)
        roles = service.get_user_roles(user_id=1)
        
        assert len(roles) == 1
        assert roles[0].code == "system_admin"
    
    def test_get_user_roles_excludes_inactive_roles(self):
        """
        测试：get_user_roles 应该排除禁用的角色
        """
        from app.services.rbac import PermissionService
        
        self.role_admin.is_active = False
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
        ]
        
        service = PermissionService(mock_db)
        roles = service.get_user_roles(user_id=1)
        
        assert len(roles) == 0
    
    def test_get_user_permissions_uses_active_roles_only(self):
        """
        测试：get_user_permissions 只从启用的角色获取权限
        """
        from app.services.rbac import PermissionService
        
        self.role_admin.is_active = False
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
        }
        mock_db._permissions = {
            1: self.perm_admin,
            2: self.perm_user,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
        ]
        mock_db._role_permissions = [
            TestRolePermission(role_id=1, permission_id=1),
            TestRolePermission(role_id=2, permission_id=2),
        ]
        
        service = PermissionService(mock_db)
        perms = service.get_user_permissions(user_id=1)
        
        assert len(perms) == 0
    
    def test_get_user_permissions_mixed_roles(self):
        """
        测试：用户同时绑定启用和禁用角色时，只返回启用角色的权限
        """
        from app.services.rbac import PermissionService
        
        self.role_auditor.is_active = False
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
            3: self.role_auditor,
        }
        mock_db._permissions = {
            1: self.perm_admin,
            2: self.perm_user,
            3: self.perm_audit,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
            TestUserRole(user_id=1, role_id=3, is_primary=False),
        ]
        mock_db._role_permissions = [
            TestRolePermission(role_id=1, permission_id=1),
            TestRolePermission(role_id=3, permission_id=3),
        ]
        
        service = PermissionService(mock_db)
        perms = service.get_user_permissions(user_id=1)
        
        assert len(perms) == 1
        assert "admin:system_config" in perms
        assert "audit:view" not in perms

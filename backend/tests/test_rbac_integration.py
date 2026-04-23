"""
RBAC服务层测试 - 菜单/权限/数据范围联动

测试目标：
- 角色与权限联动：角色禁用后权限不再生效
- 角色与菜单联动：角色禁用后菜单不再显示
- 角色与数据范围联动：角色禁用后数据范围不再生效
"""
from unittest.mock import MagicMock, patch
import pytest


class TestRole:
    def __init__(self, id, code, name, is_active=True, data_scope="self"):
        self.id = id
        self.code = code
        self.name = name
        self.is_active = is_active
        self.data_scope = data_scope


class TestPermission:
    def __init__(self, id, code, module, is_active=True):
        self.id = id
        self.code = code
        self.module = module
        self.is_active = is_active


class TestMenu:
    def __init__(self, id, code, name, path, is_active=True, is_visible=True, parent_id=None):
        self.id = id
        self.code = code
        self.name = name
        self.path = path
        self.is_active = is_active
        self.is_visible = is_visible
        self.parent_id = parent_id
        self.sort = id
        self.level = 1
        self.permission_code = None
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
    
    def order_by(self, *args):
        return self
    
    def __iter__(self):
        return iter(self._results)


class MockSession:
    def __init__(self):
        self._roles = {}
        self._permissions = {}
        self._menus = {}
        self._user_roles = []
        self._role_permissions = []
        self._role_menus = []
    
    def query(self, model_class):
        mock_query = MockQuery()
        
        model_name = getattr(model_class, '__name__', str(model_class))
        
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
        pass
    
    def delete(self, instance):
        pass


class TestRbacIntegration:
    """
    RBAC联动测试
    """
    
    def setup_method(self):
        self.role_admin = TestRole(id=1, code="system_admin", data_scope="all", is_active=True)
        self.role_user = TestRole(id=2, code="user", data_scope="self", is_active=True)
        
        self.perm_config = TestPermission(id=1, code="admin:system_config", module="admin")
        self.perm_task = TestPermission(id=2, code="task:view", module="task")
        
        self.menu_admin = TestMenu(id=1, code="admin", name="系统管理", path="/admin")
        self.menu_task = TestMenu(id=2, code="task", name="任务管理", path="/tasks")
    
    def test_role_permission_integration(self):
        """
        测试：角色与权限联动
        
        场景：
        - 系统管理员角色有 admin:system_config 权限
        - 禁用系统管理员角色后
        - 预期：该权限不再对用户生效
        """
        from app.services.rbac import PermissionService
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
        }
        mock_db._permissions = {
            1: self.perm_config,
            2: self.perm_task,
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
        
        assert "admin:system_config" in perms
    
    def test_role_disable_blocks_permission(self):
        """
        测试：禁用角色后权限不再生效
        """
        from app.services.rbac import PermissionService
        
        self.role_admin.is_active = False
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
        }
        mock_db._permissions = {
            1: self.perm_config,
            2: self.perm_task,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
        ]
        mock_db._role_permissions = [
            TestRolePermission(role_id=1, permission_id=1),
        ]
        
        service = PermissionService(mock_db)
        perms = service.get_user_permissions(user_id=1)
        
        assert len(perms) == 0
    
    def test_data_scope_service_active_roles(self):
        """
        测试：数据范围服务只从启用的角色获取数据范围
        """
        from app.services.rbac import DataScopeService
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
        ]
        
        service = DataScopeService(mock_db)
        scope = service.get_user_data_scope(user_id=1, entity_type="task")
        
        assert scope == "all"
    
    def test_data_scope_disabled_role_fallback(self):
        """
        测试：禁用角色后数据范围回退到默认值
        """
        from app.services.rbac import DataScopeService
        
        self.role_admin.is_active = False
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_user,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
        ]
        
        service = DataScopeService(mock_db)
        scope = service.get_user_data_scope(user_id=1, entity_type="task")
        
        assert scope == "self"

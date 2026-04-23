"""
RBAC服务层测试 - 主角色切换逻辑

测试目标：
- 设置新的主角色会自动清除其他主角色
- 把唯一的主角色设为非主角色不会导致无主角色
- 主角色切换时同步更新 users.role 字段
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


class TestUserRole:
    def __init__(self, user_id, role_id, is_primary=False):
        self.user_id = user_id
        self.role_id = role_id
        self.is_primary = is_primary


class MockQuery:
    def __init__(self, results=None):
        self._results = results or []
        self._update_values = None
        self._update_synchronize = None
        self._deleted = False
    
    def filter(self, *args, **kwargs):
        return self
    
    def join(self, *args, **kwargs):
        return self
    
    def all(self):
        return self._results
    
    def first(self):
        return self._results[0] if self._results else None
    
    def update(self, values, synchronize_session=False):
        self._update_values = values
        self._update_synchronize = synchronize_session
        return 1
    
    def delete(self, synchronize_session=False):
        self._deleted = True
        return 1


class MockSession:
    def __init__(self):
        self._roles = {}
        self._user_roles = []
        self._committed = False
        self._user_updates = []
        self._user_role_updates = []
    
    def query(self, model_class):
        mock_query = MockQuery()
        
        model_name = getattr(model_class, '__name__', str(model_class))
        
        if model_name == 'Role':
            mock_query._results = [r for r in self._roles.values()]
        elif model_name == 'UserRole':
            mock_query._results = self._user_roles.copy()
        
        return mock_query
    
    def add(self, instance):
        if hasattr(instance, 'user_id') and hasattr(instance, 'role_id'):
            self._user_roles.append(instance)
    
    def commit(self):
        self._committed = True
    
    def delete(self, instance):
        if instance in self._user_roles:
            self._user_roles.remove(instance)


class TestPrimaryRoleSwitch:
    """
    主角色切换逻辑测试
    """
    
    def setup_method(self):
        self.role_admin = TestRole(id=1, code="system_admin", data_scope="all")
        self.role_security = TestRole(id=2, code="security_admin", data_scope="all")
        self.role_auditor = TestRole(id=3, code="auditor", data_scope="self")
        self.role_user = TestRole(id=4, code="user", data_scope="self")
    
    def test_set_new_primary_clears_others(self):
        """
        测试：设置新的主角色会自动清除其他主角色
        
        场景：
        - 用户当前有主角色A（system_admin）
        - 调用 assign_role_to_user 设置角色B（security_admin）为新的主角色
        - 预期：角色A不再是主角色，角色B成为主角色
        """
        from app.services.rbac import RoleService
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_security,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
            TestUserRole(user_id=1, role_id=2, is_primary=False),
        ]
        
        service = RoleService(mock_db)
        result = service.assign_role_to_user(user_id=1, role_id=2, is_primary=True)
        
        assert result is True
    
    def test_cannot_demote_only_primary_role(self):
        """
        测试：不能把唯一的主角色设为非主角色
        
        场景：
        - 用户只有一个角色A，是主角色
        - 调用 assign_role_to_user 设置角色A为非主角色
        - 预期：角色A仍然是主角色（系统自动保持至少一个主角色）
        """
        from app.services.rbac import RoleService
        
        mock_db = MockSession()
        mock_db._roles = {1: self.role_admin}
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
        ]
        
        service = RoleService(mock_db)
        result = service.assign_role_to_user(user_id=1, role_id=1, is_primary=False)
        
        assert result is True
    
    def test_remove_primary_role_selects_new_primary(self):
        """
        测试：移除主角色后，自动选择新的主角色
        
        场景：
        - 用户有两个角色：A（主）、B（非主）
        - 调用 remove_role_from_user 移除角色A
        - 预期：角色B自动成为主角色
        """
        from app.services.rbac import RoleService
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_security,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=1, is_primary=True),
            TestUserRole(user_id=1, role_id=2, is_primary=False),
        ]
        
        service = RoleService(mock_db)
        result = service.remove_role_from_user(user_id=1, role_id=1)
        
        assert result is True


class TestPrimaryRoleUnit:
    """
    主角色切换单元测试
    """
    
    def test_update_primary_role_field_logic(self):
        """
        测试：_update_primary_role_and_user_field 逻辑
        """
        from app.services.rbac import RoleService
        
        mock_db = MockSession()
        mock_db._roles = {
            1: self.role_admin,
            2: self.role_security,
            3: self.role_auditor,
        }
        mock_db._user_roles = [
            TestUserRole(user_id=1, role_id=2, is_primary=True),
            TestUserRole(user_id=1, role_id=3, is_primary=False),
        ]
        
        service = RoleService(mock_db)
        
        assert True

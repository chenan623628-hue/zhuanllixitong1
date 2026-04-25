"""
RBAC服务层集成测试 - 角色禁用过滤逻辑

使用内存数据库进行真实测试
"""
import pytest


class TestRoleDisabledFilter:
    """
    角色禁用过滤测试
    
    测试目标：
    - 验证禁用角色后，权限不再下发
    - 验证禁用角色后，菜单不再显示
    - 验证禁用角色后，数据范围不再生效
    """
    
    def test_get_user_roles_filters_inactive(self, test_db, test_roles, test_user_roles):
        """
        测试：get_user_roles 应该过滤掉禁用的角色
        """
        from app.services.rbac import PermissionService
        from app.models.rbac import Role
        
        test_roles[2].is_active = False
        test_db.commit()
        
        service = PermissionService(test_db)
        roles = service.get_user_roles(user_id=1)
        
        assert len(roles) == 1
        assert roles[0].code == "system_admin"
    
    def test_get_user_permissions_uses_active_roles(self, test_db, test_roles, test_permissions, 
                                                    test_user_roles, test_role_permissions):
        """
        测试：get_user_permissions 只从启用的角色获取权限
        
        场景：
        - 用户绑定 system_admin(启用, 权限: admin:config, task:view)
        - 用户绑定 auditor(禁用, 权限: audit:view)
        - 预期：只返回 system_admin 的权限
        """
        from app.services.rbac import PermissionService
        
        test_roles[2].is_active = False
        test_db.commit()
        
        service = PermissionService(test_db)
        perms = service.get_user_permissions(user_id=1)
        
        assert len(perms) == 2
        assert "admin:system_config" in perms
        assert "task:view" in perms
        assert "audit:view" not in perms
    
    def test_get_user_menus_uses_active_roles(self, test_db, test_roles, test_menus,
                                                test_user_roles, test_role_menus):
        """
        测试：get_user_menus 只从启用的角色获取菜单
        
        场景：
        - system_admin 绑定菜单: 系统管理、任务管理
        - auditor 绑定菜单: 审计日志(禁用)
        - 预期：只返回 system_admin 的菜单
        """
        from app.services.rbac import MenuService
        
        test_roles[2].is_active = False
        test_db.commit()
        
        service = MenuService(test_db)
        menus = service.get_user_menus(user_id=1)
        
        menu_codes = [m.code for m in menus]
        assert "admin" in menu_codes
        assert "task" in menu_codes
        assert "audit" not in menu_codes
    
    def test_get_user_data_scope_uses_active_roles(self, test_db, test_roles, test_user_roles):
        """
        测试：get_user_data_scope 只从启用的角色获取数据范围
        
        场景：
        - system_admin 数据范围: all (启用)
        - auditor 数据范围: self (启用)
        - 预期：返回 all (优先级最高)
        """
        from app.services.rbac import DataScopeService
        
        service = DataScopeService(test_db)
        scope = service.get_user_data_scope(user_id=1, entity_type="task")
        
        assert scope == "all"
    
    def test_disable_primary_role_effective_scope(self, test_db, test_roles, test_user_roles):
        """
        测试：禁用主角色后数据范围回退
        
        场景：
        - system_admin 是主角色，数据范围: all (禁用)
        - auditor 是次角色，数据范围: self (启用)
        - 预期：返回 self
        """
        from app.services.rbac import DataScopeService
        
        test_roles[0].is_active = False
        test_db.commit()
        
        service = DataScopeService(test_db)
        scope = service.get_user_data_scope(user_id=1, entity_type="task")
        
        assert scope == "self"
    
    def test_disable_all_roles_fallback(self, test_db, test_roles, test_user_roles):
        """
        测试：禁用所有角色后回退到默认值
        
        场景：
        - 禁用用户的所有角色
        - 预期：数据范围回退到 self
        """
        from app.services.rbac import DataScopeService
        
        for role in test_roles:
            role.is_active = False
        test_db.commit()
        
        service = DataScopeService(test_db)
        scope = service.get_user_data_scope(user_id=1, entity_type="task")
        
        assert scope == "self"


class TestRoleDisabledPermissions:
    """
    角色禁用后的权限检查测试
    """
    
    def test_is_system_admin_returns_false_after_disable(self, test_db, test_roles, test_user_roles):
        """
        测试：禁用 system_admin 角色后，is_system_admin 返回 False
        """
        from app.services.rbac import PermissionService
        
        test_roles[0].is_active = False
        test_db.commit()
        
        service = PermissionService(test_db)
        
        assert service.is_system_admin(user_id=1) is False
    
    def test_is_system_admin_returns_true_when_active(self, test_db, test_roles, test_user_roles):
        """
        测试：system_admin 角色启用时，is_system_admin 返回 True
        """
        from app.services.rbac import PermissionService
        
        service = PermissionService(test_db)
        
        assert service.is_system_admin(user_id=1) is True
    
    def test_has_permission_checks_active_roles(self, test_db, test_roles, test_permissions,
                                                 test_user_roles, test_role_permissions):
        """
        测试：has_permission 只检查启用角色的权限
        """
        from app.services.rbac import PermissionService
        
        service = PermissionService(test_db)
        
        assert service.has_permission(user_id=1, permission_code="admin:system_config") is True
        assert service.has_permission(user_id=1, permission_code="audit:view") is True
        
        test_roles[0].is_active = False
        test_db.commit()
        
        assert service.has_permission(user_id=1, permission_code="admin:system_config") is False
        assert service.has_permission(user_id=1, permission_code="audit:view") is True

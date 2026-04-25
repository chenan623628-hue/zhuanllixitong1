"""
RBAC服务层集成测试 - 主角色切换逻辑

使用内存数据库进行真实测试

测试数据说明 (来自 test_user_roles fixture):
- 用户1: role_id=1(system_admin, 主), role_id=3(auditor, 非主)
- 用户2: role_id=4(user, 主)
"""
import pytest


class TestPrimaryRoleSwitch:
    """
    主角色切换集成测试
    
    测试目标：
    - 设置新的主角色会自动清除其他主角色
    - 把唯一的主角色设为非主角色不会导致无主角色
    - 移除主角色后自动选择新的主角色
    """
    
    def test_assign_new_primary_clears_others(self, test_db, test_roles, test_user_roles):
        """
        测试：设置新的主角色会自动清除其他主角色
        
        场景：
        - 用户1当前：system_admin(主)、auditor(非主)
        - 调用 assign_role_to_user 设置 auditor 为新的主角色
        - 预期：system_admin 不再是主角色，auditor 成为主角色
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        result = service.assign_role_to_user(user_id=1, role_id=3, is_primary=True)
        
        assert result is True
        
        user_roles = test_db.query(UserRole).filter(UserRole.user_id == 1).all()
        
        system_admin_role = next((r for r in user_roles if r.role_id == 1), None)
        auditor_role = next((r for r in user_roles if r.role_id == 3), None)
        
        assert system_admin_role is not None
        assert auditor_role is not None
        assert system_admin_role.is_primary is False
        assert auditor_role.is_primary is True
    
    def test_assign_primary_to_new_role(self, test_db, test_roles, test_user_roles):
        """
        测试：给用户分配新角色并设为主角色
        
        场景：
        - 用户2当前：只有 user(主)
        - 给用户2分配 system_admin 并设为主角色
        - 预期：user 变为非主，system_admin 成为主
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        result = service.assign_role_to_user(user_id=2, role_id=1, is_primary=True)
        
        assert result is True
        
        user_roles = test_db.query(UserRole).filter(UserRole.user_id == 2).all()
        
        user_role_record = next((r for r in user_roles if r.role_id == 4), None)
        admin_role_record = next((r for r in user_roles if r.role_id == 1), None)
        
        assert user_role_record is not None
        assert admin_role_record is not None
        assert user_role_record.is_primary is False
        assert admin_role_record.is_primary is True
    
    def test_remove_primary_role_selects_new_one(self, test_db, test_roles, test_user_roles):
        """
        测试：移除主角色后自动选择新的主角色
        
        场景：
        - 用户1当前：system_admin(主)、auditor(非主)
        - 移除 system_admin
        - 预期：auditor 自动成为主角色
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        result = service.remove_role_from_user(user_id=1, role_id=1)
        
        assert result is True
        
        remaining_roles = test_db.query(UserRole).filter(UserRole.user_id == 1).all()
        
        assert len(remaining_roles) == 1
        assert remaining_roles[0].role_id == 3
        assert remaining_roles[0].is_primary is True
    
    def test_assign_non_primary_to_existing_primary(self, test_db, test_roles, test_user_roles):
        """
        测试：把唯一的主角色设为非主角色
        
        场景：
        - 用户2只有 user(主) 这一个角色
        - 调用 assign_role_to_user 设置 user 为非主角色
        - 预期：user 仍然是主角色（系统自动保持至少一个主角色）
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        result = service.assign_role_to_user(user_id=2, role_id=4, is_primary=False)
        
        assert result is True
        
        user_roles = test_db.query(UserRole).filter(UserRole.user_id == 2).all()
        
        assert len(user_roles) == 1
        assert user_roles[0].is_primary is True
    
    def test_demote_primary_but_other_roles_exist(self, test_db, test_roles, test_user_roles):
        """
        测试：把主角色设为非主，但存在其他角色
        
        场景：
        - 用户1当前：system_admin(主)、auditor(非主)
        - 把 system_admin 设为非主
        - 预期：auditor 自动成为主角色
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        result = service.assign_role_to_user(user_id=1, role_id=1, is_primary=False)
        
        assert result is True
        
        user_roles = test_db.query(UserRole).filter(UserRole.user_id == 1).all()
        
        system_admin_role = next((r for r in user_roles if r.role_id == 1), None)
        auditor_role = next((r for r in user_roles if r.role_id == 3), None)
        
        assert system_admin_role.is_primary is False
        assert auditor_role.is_primary is True


class TestPrimaryRoleBoundary:
    """
    主角色边界测试
    """
    
    def test_remove_all_roles(self, test_db, test_roles, test_user_roles):
        """
        测试：移除用户的所有角色
        
        场景：
        - 用户1有两个角色
        - 移除所有角色
        - 预期：UserRole 表中没有该用户的记录
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        
        service.remove_role_from_user(user_id=1, role_id=1)
        service.remove_role_from_user(user_id=1, role_id=3)
        
        remaining = test_db.query(UserRole).filter(UserRole.user_id == 1).all()
        
        assert len(remaining) == 0
    
    def test_assign_non_primary_when_no_primary_exists(self, test_db, test_roles):
        """
        测试：分配非主角色时，如果用户没有主角色，自动设为主角色
        
        场景：
        - 用户3没有任何角色
        - 分配 user 角色为非主
        - 预期：由于没有其他角色，user 自动成为主角色
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        result = service.assign_role_to_user(user_id=3, role_id=4, is_primary=False)
        
        assert result is True
        
        user_roles = test_db.query(UserRole).filter(UserRole.user_id == 3).all()
        
        assert len(user_roles) == 1
        assert user_roles[0].is_primary is True
    
    def test_assign_multiple_roles_sequentially(self, test_db, test_roles, test_user_roles):
        """
        测试：依次分配多个角色为主
        
        场景：
        - 用户2当前：user(主)
        - 分配 system_admin 为主 → user变非主
        - 分配 auditor 为主 → system_admin变非主
        - 预期：auditor 是唯一的主角色
        """
        from app.services.rbac import RoleService
        from app.models.rbac import UserRole
        
        service = RoleService(test_db)
        
        service.assign_role_to_user(user_id=2, role_id=1, is_primary=True)
        
        service.assign_role_to_user(user_id=2, role_id=3, is_primary=True)
        
        user_roles = test_db.query(UserRole).filter(UserRole.user_id == 2).all()
        
        primary_roles = [r for r in user_roles if r.is_primary]
        
        assert len(primary_roles) == 1
        assert primary_roles[0].role_id == 3

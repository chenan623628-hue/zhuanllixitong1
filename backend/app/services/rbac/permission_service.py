"""
专利-标准比对系统 V1.0
M03 RBAC与权限域模块 - 权限服务
"""
import json
import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.rbac import (
    Role, Permission, RolePermission,
    Menu, RoleMenu, UserRole,
    BuiltinRoles, BuiltinPermissions, RolePermissionMatrix
)
from app.models.user import User

logger = logging.getLogger(__name__)


class PermissionService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_permissions(self, user_id: int) -> list[str]:
        """
        获取用户的所有权限码
        """
        user_roles = self.db.query(UserRole).filter(
            UserRole.user_id == user_id
        ).all()
        
        if not user_roles:
            return []
        
        role_ids = [ur.role_id for ur in user_roles]
        
        role_permissions = self.db.query(RolePermission).filter(
            RolePermission.role_id.in_(role_ids)
        ).all()
        
        if not role_permissions:
            return []
        
        permission_ids = [rp.permission_id for rp in role_permissions]
        
        permissions = self.db.query(Permission).filter(
            Permission.id.in_(permission_ids),
            Permission.is_active == True
        ).all()
        
        return [p.code for p in permissions]
    
    def has_permission(self, user_id: int, permission_code: str) -> bool:
        """
        检查用户是否具有指定权限
        """
        permissions = self.get_user_permissions(user_id)
        return permission_code in permissions
    
    def has_any_permission(self, user_id: int, permission_codes: list[str]) -> bool:
        """
        检查用户是否具有任一权限
        """
        permissions = self.get_user_permissions(user_id)
        return any(p in permissions for p in permission_codes)
    
    def has_all_permissions(self, user_id: int, permission_codes: list[str]) -> bool:
        """
        检查用户是否具有所有权限
        """
        permissions = self.get_user_permissions(user_id)
        return all(p in permissions for p in permission_codes)
    
    def get_user_roles(self, user_id: int) -> list[Role]:
        """
        获取用户的所有角色
        """
        user_roles = self.db.query(UserRole).filter(
            UserRole.user_id == user_id
        ).all()
        
        if not user_roles:
            return []
        
        role_ids = [ur.role_id for ur in user_roles]
        
        roles = self.db.query(Role).filter(
            Role.id.in_(role_ids),
            Role.is_active == True
        ).all()
        
        return roles
    
    def get_user_role_codes(self, user_id: int) -> list[str]:
        """
        获取用户的所有角色代码
        """
        roles = self.get_user_roles(user_id)
        return [r.code for r in roles]
    
    def is_system_admin(self, user_id: int) -> bool:
        """
        检查用户是否是系统管理员
        """
        role_codes = self.get_user_role_codes(user_id)
        return "system_admin" in role_codes
    
    def is_security_admin(self, user_id: int) -> bool:
        """
        检查用户是否是安全管理员
        """
        role_codes = self.get_user_role_codes(user_id)
        return "security_admin" in role_codes
    
    def is_auditor(self, user_id: int) -> bool:
        """
        检查用户是否是审计管理员
        """
        role_codes = self.get_user_role_codes(user_id)
        return "auditor" in role_codes
    
    def has_audit_access(self, user_id: int) -> bool:
        """
        检查用户是否有审计访问权限（仅审计管理员）
        """
        return self.is_auditor(user_id)
    
    def has_system_config_access(self, user_id: int) -> bool:
        """
        检查用户是否有系统配置权限（系统管理员）
        注意：审计管理员不应有此权限
        """
        if self.is_auditor(user_id):
            return False
        return self.is_system_admin(user_id)
    
    def has_security_config_access(self, user_id: int) -> bool:
        """
        检查用户是否有安全配置权限（安全管理员）
        注意：审计管理员不应有此权限
        """
        if self.is_auditor(user_id):
            return False
        return self.is_security_admin(user_id)


class MenuService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_all_menus(self, include_invisible: bool = False) -> list[Menu]:
        """
        获取所有菜单
        """
        query = self.db.query(Menu).filter(Menu.is_active == True)
        
        if not include_invisible:
            query = query.filter(Menu.is_visible == True)
        
        return query.order_by(Menu.level, Menu.sort).all()
    
    def get_user_menus(self, user_id: int) -> list[Menu]:
        """
        获取用户可见的菜单树
        """
        user_roles = self.db.query(UserRole).filter(
            UserRole.user_id == user_id
        ).all()
        
        if not user_roles:
            return []
        
        role_ids = [ur.role_id for ur in user_roles]
        
        role_menus = self.db.query(RoleMenu).filter(
            RoleMenu.role_id.in_(role_ids)
        ).all()
        
        if not role_menus:
            return []
        
        menu_ids = [rm.menu_id for rm in role_menus]
        
        menus = self.db.query(Menu).filter(
            Menu.id.in_(menu_ids),
            Menu.is_active == True,
            Menu.is_visible == True
        ).order_by(Menu.level, Menu.sort).all()
        
        parent_ids = [m.parent_id for m in menus if m.parent_id]
        if parent_ids:
            parent_menus = self.db.query(Menu).filter(
                Menu.id.in_(parent_ids),
                Menu.is_active == True,
                Menu.is_visible == True
            ).all()
            for pm in parent_menus:
                if pm.id not in [m.id for m in menus]:
                    menus.append(pm)
        
        return sorted(menus, key=lambda m: (m.level, m.sort))
    
    def build_menu_tree(self, menus: list[Menu]) -> list[dict]:
        """
        构建菜单树结构
        """
        menu_map = {}
        for menu in menus:
            menu_map[menu.id] = {
                "id": menu.id,
                "name": menu.name,
                "code": menu.code,
                "path": menu.path,
                "icon": menu.icon,
                "sort": menu.sort,
                "level": menu.level,
                "permission_code": menu.permission_code,
                "component": menu.component,
                "children": [],
            }
        
        root_menus = []
        for menu in menus:
            menu_data = menu_map[menu.id]
            if menu.parent_id and menu.parent_id in menu_map:
                menu_map[menu.parent_id]["children"].append(menu_data)
            else:
                root_menus.append(menu_data)
        
        def sort_children(items):
            items.sort(key=lambda x: x["sort"])
            for item in items:
                if item["children"]:
                    sort_children(item["children"])
        
        sort_children(root_menus)
        return root_menus
    
    def get_user_menu_tree(self, user_id: int) -> list[dict]:
        """
        获取用户的菜单树
        """
        menus = self.get_user_menus(user_id)
        return self.build_menu_tree(menus)


class RoleService:
    def __init__(self, db: Session):
        self.db = db
    
    def init_builtin_roles(self) -> None:
        """
        初始化内置角色和权限
        """
        existing_roles = self.db.query(Role).filter(
            Role.is_builtin == True
        ).all()
        
        existing_role_codes = {r.code for r in existing_roles}
        
        builtin_roles = [
            BuiltinRoles.SYSTEM_ADMIN,
            BuiltinRoles.SECURITY_ADMIN,
            BuiltinRoles.AUDITOR,
            BuiltinRoles.USER,
        ]
        
        for role_data in builtin_roles:
            if role_data["code"] not in existing_role_codes:
                role = Role(
                    name=role_data["name"],
                    code=role_data["code"],
                    description=role_data["description"],
                    is_builtin=role_data["is_builtin"],
                    data_scope=role_data["data_scope"],
                    is_active=True,
                )
                self.db.add(role)
        
        self.db.commit()
        
        existing_perms = self.db.query(Permission).all()
        existing_perm_codes = {p.code for p in existing_perms}
        
        builtin_perms = BuiltinPermissions.get_permissions()
        for perm_data in builtin_perms:
            if perm_data["code"] not in existing_perm_codes:
                perm = Permission(
                    name=perm_data["name"],
                    code=perm_data["code"],
                    module=perm_data["module"],
                    action=perm_data["action"],
                    description=perm_data["description"],
                    is_active=True,
                )
                self.db.add(perm)
        
        self.db.commit()
        
        self._init_role_permissions()
    
    def _init_role_permissions(self) -> None:
        """
        初始化角色权限关联
        """
        roles = self.db.query(Role).all()
        role_map = {r.code: r for r in roles}
        
        permissions = self.db.query(Permission).all()
        perm_map = {p.code: p for p in permissions}
        
        matrix = RolePermissionMatrix.get_all_matrix()
        
        for role_code, perm_codes in matrix.items():
            if role_code not in role_map:
                continue
            
            role = role_map[role_code]
            
            existing_rps = self.db.query(RolePermission).filter(
                RolePermission.role_id == role.id
            ).all()
            existing_perm_ids = {rp.permission_id for rp in existing_rps}
            
            for perm_code in perm_codes:
                if perm_code not in perm_map:
                    continue
                
                perm = perm_map[perm_code]
                if perm.id not in existing_perm_ids:
                    rp = RolePermission(role_id=role.id, permission_id=perm.id)
                    self.db.add(rp)
        
        self.db.commit()
    
    def assign_role_to_user(self, user_id: int, role_id: int, is_primary: bool = False) -> bool:
        """
        为用户分配角色
        注意：如果设置 is_primary=True，会自动清除该用户其他角色的 is_primary 标记
        """
        if is_primary:
            self.db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id != role_id,
                UserRole.is_primary == True
            ).update({"is_primary": False}, synchronize_session=False)
        
        existing = self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        ).first()
        
        if existing:
            existing.is_primary = is_primary
            self.db.commit()
            return True
        
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            is_primary=is_primary,
        )
        self.db.add(user_role)
        self.db.commit()
        return True
    
    def remove_role_from_user(self, user_id: int, role_id: int) -> bool:
        """
        移除用户角色
        """
        user_role = self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        ).first()
        
        if user_role:
            self.db.delete(user_role)
            self.db.commit()
            return True
        return False


class DataScopeService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_data_scope(self, user_id: int, entity_type: str) -> str:
        """
        获取用户的数据范围
        """
        user_roles = self.db.query(UserRole).filter(
            UserRole.user_id == user_id
        ).all()
        
        if not user_roles:
            return "self"
        
        role_ids = [ur.role_id for ur in user_roles]
        
        scopes = []
        for role_id in role_ids:
            role = self.db.query(Role).filter(Role.id == role_id).first()
            if role:
                scopes.append(role.data_scope)
        
        priority = ["all", "dept", "self"]
        for s in priority:
            if s in scopes:
                return s
        
        return "self"
    
    def apply_data_scope_filter(
        self, 
        query, 
        model_class, 
        user_id: int, 
        entity_type: str,
        owner_id_column: str = "user_id"
    ):
        """
        应用数据范围过滤
        """
        scope = self.get_user_data_scope(user_id, entity_type)
        
        if scope == "all":
            return query
        
        owner_column = getattr(model_class, owner_id_column)
        
        if scope == "self":
            return query.filter(owner_column == user_id)
        
        if scope == "dept":
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and hasattr(user, 'dept_id') and user.dept_id:
                return query.filter(
                    model_class.dept_id == user.dept_id
                )
            return query.filter(owner_column == user_id)
        
        return query
    
    def can_access_entity(
        self, 
        user_id: int, 
        entity_type: str, 
        entity_owner_id: int,
        entity_dept_id: int | None = None
    ) -> bool:
        """
        检查用户是否可以访问指定实体
        """
        scope = self.get_user_data_scope(user_id, entity_type)
        
        if scope == "all":
            return True
        
        if scope == "self":
            return entity_owner_id == user_id
        
        if scope == "dept":
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and hasattr(user, 'dept_id') and user.dept_id:
                return entity_dept_id == user.dept_id
            return entity_owner_id == user_id
        
        return False

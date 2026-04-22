"""
专利-标准比对系统 V1.0
M03 RBAC与权限域模块 - 数据范围过滤器
"""
import json
import logging
from enum import Enum
from typing import Any, Callable, TypeVar, Generic

from sqlalchemy.orm import Query, Session
from sqlalchemy import Column, and_, or_

from app.models.rbac import (
    Role, UserRole, RoleDataScope, DataScopePolicy
)
from app.models.user import User

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DataScopeType(str, Enum):
    SELF = "self"
    DEPT = "dept"
    CUSTOM = "custom"
    ALL = "all"


class EntityType(str, Enum):
    USER = "user"
    TASK = "task"
    FILE = "file"
    REPORT = "report"
    RULE = "rule"
    TERM = "term"
    AUDIT = "audit"


class DataScopeFilter:
    """
    数据范围过滤器
    
    实现三员分离的数据范围控制：
    - self: 仅自己的数据
    - dept: 本部门的数据
    - all: 所有数据
    """
    
    def __init__(self, db: Session, current_user_id: int):
        self.db = db
        self.current_user_id = current_user_id
        self._user_role = None
        self._user_data_scope = None
        self._dept_id = None
    
    def _get_user_role(self) -> Role | None:
        """获取用户主角色"""
        if self._user_role is not None:
            return self._user_role
        
        user = self.db.query(User).filter(User.id == self.current_user_id).first()
        if user:
            role = self.db.query(Role).filter(
                Role.code == user.role
            ).first()
            if role:
                self._user_role = role
                return role
        
        user_role = self.db.query(UserRole).filter(
            UserRole.user_id == self.current_user_id,
            UserRole.is_primary == True
        ).first()
        
        if user_role:
            role = self.db.query(Role).filter(
                Role.id == user_role.role_id
            ).first()
            self._user_role = role
            return role
        
        user_roles = self.db.query(UserRole).filter(
            UserRole.user_id == self.current_user_id
        ).first()
        
        if user_roles:
            role = self.db.query(Role).filter(
                Role.id == user_roles.role_id
            ).first()
            self._user_role = role
            return role
        
        return None
    
    def _get_data_scope(self, entity_type: str | None = None) -> str:
        """
        获取用户的数据范围
        
        优先级：
        1. 角色数据范围关联表中特定实体类型的配置
        2. 角色表中的默认 data_scope
        """
        if self._user_data_scope is not None and not entity_type:
            return self._user_data_scope
        
        role = self._get_user_role()
        if not role:
            return DataScopeType.SELF.value
        
        if entity_type:
            role_data_scope = self.db.query(RoleDataScope).filter(
                RoleDataScope.role_id == role.id,
                RoleDataScope.entity_type == entity_type
            ).first()
            
            if role_data_scope:
                if role_data_scope.data_scope_policy_id:
                    policy = self.db.query(DataScopePolicy).filter(
                        DataScopePolicy.id == role_data_scope.data_scope_policy_id
                    ).first()
                    if policy:
                        return policy.scope_type
                return DataScopeType.SELF.value
        
        default_scope = role.data_scope or DataScopeType.SELF.value
        if not entity_type:
            self._user_data_scope = default_scope
        return default_scope
    
    def apply(
        self,
        query: Query[T],
        entity_type: str | None = None,
        user_id_column: Column | None = None,
        dept_id_column: Column | None = None,
        custom_filter: Callable[[Any], Any] | None = None,
    ) -> Query[T]:
        """
        应用数据范围过滤到查询
        
        Args:
            query: SQLAlchemy 查询对象
            entity_type: 实体类型（用于查找特定实体的配置）
            user_id_column: 表中表示创建者的列（如 Task.created_by）
            dept_id_column: 表中表示部门的列（如 Task.dept_id）
            custom_filter: 自定义过滤条件生成器
        
        Returns:
            应用了数据范围过滤的查询对象
        """
        data_scope = self._get_data_scope(entity_type)
        logger.info(
            f"Applying data scope filter: user_id={self.current_user_id}, "
            f"entity_type={entity_type}, scope={data_scope}"
        )
        
        if data_scope == DataScopeType.ALL.value:
            return query
        
        if data_scope == DataScopeType.SELF.value:
            if user_id_column is not None:
                return query.filter(user_id_column == self.current_user_id)
            if custom_filter:
                condition = custom_filter(DataScopeType.SELF)
                if condition is not None:
                    return query.filter(condition)
            return query.filter(False)
        
        if data_scope == DataScopeType.DEPT.value:
            user_dept_id = self._get_user_dept_id()
            
            if dept_id_column is not None and user_dept_id:
                return query.filter(dept_id_column == user_dept_id)
            
            if user_id_column is not None:
                dept_user_ids = self._get_dept_user_ids()
                if dept_user_ids:
                    return query.filter(user_id_column.in_(dept_user_ids))
            
            if custom_filter:
                condition = custom_filter(DataScopeType.DEPT)
                if condition is not None:
                    return query.filter(condition)
            
            return query.filter(user_id_column == self.current_user_id)
        
        if data_scope == DataScopeType.CUSTOM.value:
            role = self._get_user_role()
            if role and entity_type:
                role_data_scope = self.db.query(RoleDataScope).filter(
                    RoleDataScope.role_id == role.id,
                    RoleDataScope.entity_type == entity_type
                ).first()
                
                if role_data_scope:
                    conditions = []
                    
                    if role_data_scope.custom_user_ids:
                        try:
                            user_ids = json.loads(role_data_scope.custom_user_ids)
                            if user_ids and user_id_column is not None:
                                conditions.append(user_id_column.in_(user_ids))
                        except json.JSONDecodeError:
                            pass
                    
                    if role_data_scope.custom_dept_ids:
                        try:
                            dept_ids = json.loads(role_data_scope.custom_dept_ids)
                            if dept_ids and dept_id_column is not None:
                                conditions.append(dept_id_column.in_(dept_ids))
                        except json.JSONDecodeError:
                            pass
                    
                    if conditions:
                        return query.filter(or_(*conditions))
            
            if custom_filter:
                condition = custom_filter(DataScopeType.CUSTOM)
                if condition is not None:
                    return query.filter(condition)
            
            return query.filter(user_id_column == self.current_user_id)
        
        return query
    
    def _get_user_dept_id(self) -> int | None:
        """获取用户所在部门ID"""
        if self._dept_id is not None:
            return self._dept_id
        
        user = self.db.query(User).filter(User.id == self.current_user_id).first()
        if user and hasattr(user, 'dept_id'):
            self._dept_id = user.dept_id
            return user.dept_id
        
        return None
    
    def _get_dept_user_ids(self) -> list[int]:
        """获取同部门所有用户ID"""
        dept_id = self._get_user_dept_id()
        if not dept_id:
            return [self.current_user_id]
        
        if hasattr(User, 'dept_id'):
            users = self.db.query(User.id).filter(
                User.dept_id == dept_id,
                User.is_active == True
            ).all()
            return [u[0] for u in users]
        
        return [self.current_user_id]
    
    def can_access(
        self,
        entity_id: int,
        entity_type: str,
        get_entity_func: Callable[[Session, int], Any],
        user_id_attr: str = "created_by",
        dept_id_attr: str | None = None,
    ) -> bool:
        """
        检查用户是否可以访问某个实体
        
        Args:
            entity_id: 实体ID
            entity_type: 实体类型
            get_entity_func: 获取实体的函数 (db, id) -> entity
            user_id_attr: 实体中表示用户ID的属性名
            dept_id_attr: 实体中表示部门ID的属性名（可选）
        
        Returns:
            是否有权限访问
        """
        data_scope = self._get_data_scope(entity_type)
        
        if data_scope == DataScopeType.ALL.value:
            return True
        
        entity = get_entity_func(self.db, entity_id)
        if not entity:
            return False
        
        if data_scope == DataScopeType.SELF.value:
            entity_user_id = getattr(entity, user_id_attr, None)
            return entity_user_id == self.current_user_id
        
        if data_scope == DataScopeType.DEPT.value:
            entity_user_id = getattr(entity, user_id_attr, None)
            if entity_user_id == self.current_user_id:
                return True
            
            if dept_id_attr:
                entity_dept_id = getattr(entity, dept_id_attr, None)
                user_dept_id = self._get_user_dept_id()
                if entity_dept_id and user_dept_id and entity_dept_id == user_dept_id:
                    return True
            
            dept_user_ids = self._get_dept_user_ids()
            return entity_user_id in dept_user_ids
        
        if data_scope == DataScopeType.CUSTOM.value:
            role = self._get_user_role()
            if role:
                role_data_scope = self.db.query(RoleDataScope).filter(
                    RoleDataScope.role_id == role.id,
                    RoleDataScope.entity_type == entity_type
                ).first()
                
                if role_data_scope:
                    entity_user_id = getattr(entity, user_id_attr, None)
                    
                    if role_data_scope.custom_user_ids:
                        try:
                            user_ids = json.loads(role_data_scope.custom_user_ids)
                            if entity_user_id in user_ids:
                                return True
                        except json.JSONDecodeError:
                            pass
                    
                    if dept_id_attr and role_data_scope.custom_dept_ids:
                        entity_dept_id = getattr(entity, dept_id_attr, None)
                        try:
                            dept_ids = json.loads(role_data_scope.custom_dept_ids)
                            if entity_dept_id in dept_ids:
                                return True
                        except json.JSONDecodeError:
                            pass
            
            return False
        
        return False


def create_data_scope_filter(db: Session, current_user_id: int) -> DataScopeFilter:
    """
    创建数据范围过滤器的工厂函数
    
    使用示例：
    ```python
    @router.get("/tasks")
    async def get_tasks(
        db: Session = Depends(get_db),
        current_user: CurrentUser = Depends(get_current_user)
    ):
        filter = create_data_scope_filter(db, current_user.id)
        query = db.query(Task)
        query = filter.apply(query, "task", Task.created_by)
        tasks = query.all()
        return tasks
    ```
    """
    return DataScopeFilter(db, current_user_id)

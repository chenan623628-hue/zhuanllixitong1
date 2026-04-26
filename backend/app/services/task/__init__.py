"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - 任务服务包
"""
from app.services.task.task_service import (
    TaskService, 
    CreateTaskContext, 
    UpdateProgressContext,
    DEFAULT_LEASE_DURATION_SECONDS,
    HEARTBEAT_EXTEND_SECONDS,
)
from app.services.task.event_service import EventService
from app.services.task.state_machine_service import StateMachineService, TransitionResult

__all__ = [
    "TaskService",
    "CreateTaskContext",
    "UpdateProgressContext",
    "DEFAULT_LEASE_DURATION_SECONDS",
    "HEARTBEAT_EXTEND_SECONDS",
    "EventService",
    "StateMachineService",
    "TransitionResult",
]

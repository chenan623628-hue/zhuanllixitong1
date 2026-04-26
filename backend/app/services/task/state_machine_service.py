"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - 任务状态机服务
"""
import logging
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.task import (
    Task, TaskEvent, TaskStatus, TaskStatusTransition, 
    TaskEventType, TaskStep, StateMachine
)
from app.core.schemas import ErrorCode
from app.core.exceptions import TaskException

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class TransitionResult:
    success: bool
    from_status: str
    to_status: str
    message: str = ""
    event: TaskEvent | None = None


class StateMachineService:
    def __init__(self, db: Session):
        self.db = db
    
    def can_transition(self, task: Task, to_status: str) -> bool:
        return TaskStatusTransition.can_transition(task.status, to_status)
    
    def validate_transition(self, task: Task, to_status: str) -> None:
        if not self.can_transition(task, to_status):
            raise TaskException(
                code=ErrorCode.TASK_STATUS_INVALID,
                message=f"无法从状态 '{task.status}' 转移到 '{to_status}'"
            )
    
    def transition(
        self,
        task: Task,
        to_status: str,
        event_message: str = "",
        user_id: int | None = None,
        worker_id: str | None = None,
        progress_percent: int | None = None,
        progress_message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        step_name: str | None = None,
        step_duration: int | None = None,
        event_details: dict[str, Any] | None = None,
    ) -> TransitionResult:
        from_status = task.status
        
        self.validate_transition(task, to_status)
        
        task.previous_status = from_status
        task.status = to_status
        
        now = _utcnow()
        
        if to_status == TaskStatus.PARSING:
            task.started_at = now
            task.progress_percent = progress_percent or 10
        elif to_status == TaskStatus.COMPARING:
            task.parsing_completed_at = now
            task.progress_percent = progress_percent or 30
        elif to_status == TaskStatus.REVIEW_PENDING:
            task.comparing_completed_at = now
            task.progress_percent = progress_percent or 70
        elif to_status == TaskStatus.REVIEWED:
            task.review_completed_at = now
            task.progress_percent = progress_percent or 85
        elif to_status == TaskStatus.REPORT_READY:
            task.report_completed_at = now
            task.progress_percent = progress_percent or 95
        elif to_status == TaskStatus.ARCHIVED:
            task.completed_at = now
            task.progress_percent = 100
            task.is_archived = True
            if task.started_at:
                task.actual_duration_seconds = int((now - task.started_at).total_seconds())
        elif to_status == TaskStatus.FAILED:
            task.failed_at = now
            task.error_code = error_code
            task.error_message = error_message
        elif to_status == TaskStatus.CANCELLED:
            task.cancelled_at = now
        elif to_status == TaskStatus.PENDING:
            if from_status in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                task.retry_count += 1
                task.error_code = None
                task.error_message = None
                task.progress_percent = 0
        
        if progress_percent is not None:
            task.progress_percent = min(max(progress_percent, 0), 100)
        if progress_message:
            task.progress_message = progress_message
        
        event_type = StateMachine.get_event_for_transition(from_status, to_status) or TaskEventType.STATUS_CHANGE
        
        event = TaskEvent(
            event_type=event_type,
            event_time=now,
            task_id=task.task_id,
            from_status=from_status,
            to_status=to_status,
            event_message=event_message or f"状态变更: {from_status} -> {to_status}",
            progress_percent=progress_percent,
            progress_message=progress_message,
            user_id=user_id,
            worker_id=worker_id,
            error_code=error_code,
            error_message=error_message,
            step_name=step_name,
            step_duration_seconds=step_duration,
        )
        if event_details:
            event.set_event_details(event_details)
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(task)
        
        logger.info(f"Task {task.task_id} transition: {from_status} -> {to_status}")
        
        return TransitionResult(
            success=True,
            from_status=from_status,
            to_status=to_status,
            message=f"状态变更成功: {from_status} -> {to_status}",
            event=event,
        )
    
    def cancel_task(
        self,
        task: Task,
        reason: str = "",
        user_id: int | None = None,
    ) -> TransitionResult:
        if not TaskStatusTransition.is_cancellable(task.status):
            raise TaskException(
                code=ErrorCode.TASK_CANCEL_FAILED,
                message=f"任务状态 '{task.status}' 无法取消"
            )
        
        return self.transition(
            task=task,
            to_status=TaskStatus.CANCELLED,
            event_message=reason or "用户取消任务",
            user_id=user_id,
        )
    
    def retry_task(
        self,
        task: Task,
        user_id: int | None = None,
        worker_id: str | None = None,
    ) -> TransitionResult:
        if not TaskStatusTransition.is_retryable(task.status):
            raise TaskException(
                code=ErrorCode.TASK_STATUS_INVALID,
                message=f"任务状态 '{task.status}' 无法重试"
            )
        
        if task.retry_count >= task.max_retries:
            raise TaskException(
                code=ErrorCode.TASK_STATUS_INVALID,
                message=f"任务已达到最大重试次数 ({task.max_retries})"
            )
        
        return self.transition(
            task=task,
            to_status=TaskStatus.PENDING,
            event_message=f"重试任务 (第 {task.retry_count + 1} 次)",
            user_id=user_id,
            worker_id=worker_id,
        )
    
    def mark_as_failed(
        self,
        task: Task,
        error_code: str,
        error_message: str,
        worker_id: str | None = None,
    ) -> TransitionResult:
        return self.transition(
            task=task,
            to_status=TaskStatus.FAILED,
            event_message=f"任务失败: {error_message}",
            worker_id=worker_id,
            error_code=error_code,
            error_message=error_message,
        )
    
    def update_progress(
        self,
        task: Task,
        progress_percent: int,
        progress_message: str | None = None,
        step_name: str | None = None,
        step_duration: int | None = None,
        worker_id: str | None = None,
    ) -> TaskEvent:
        progress_percent = min(max(progress_percent, 0), 100)
        task.progress_percent = progress_percent
        
        if progress_message:
            task.progress_message = progress_message
        
        event = TaskEvent(
            event_type=TaskEventType.PROGRESS_UPDATE,
            event_time=_utcnow(),
            task_id=task.task_id,
            from_status=task.status,
            to_status=task.status,
            event_message=progress_message or f"进度更新: {progress_percent}%",
            progress_percent=progress_percent,
            progress_message=progress_message,
            worker_id=worker_id,
            step_name=step_name,
            step_duration_seconds=step_duration,
        )
        
        self.db.add(event)
        self.db.commit()
        
        logger.debug(f"Task {task.task_id} progress: {progress_percent}%")
        
        return event
    
    def record_step(
        self,
        task: Task,
        step_name: str,
        progress_percent: int,
        step_duration: int | None = None,
        step_details: dict[str, Any] | None = None,
        worker_id: str | None = None,
    ) -> TaskEvent:
        progress_percent = min(max(progress_percent, 0), 100)
        
        event = TaskEvent(
            event_type=TaskEventType.STEP_COMPLETED,
            event_time=_utcnow(),
            task_id=task.task_id,
            from_status=task.status,
            to_status=task.status,
            event_message=f"步骤完成: {step_name}",
            progress_percent=progress_percent,
            worker_id=worker_id,
            step_name=step_name,
            step_duration_seconds=step_duration,
        )
        
        if step_details:
            event.set_event_details(step_details)
        
        self.db.add(event)
        self.db.commit()
        
        logger.info(f"Task {task.task_id} step completed: {step_name}")
        
        return event
    
    def get_task_status_summary(self, task: Task) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "status": task.status,
            "previous_status": task.previous_status,
            "progress_percent": task.progress_percent,
            "progress_message": task.progress_message,
            "is_final": TaskStatusTransition.is_final(task.status),
            "is_running": TaskStatusTransition.is_running(task.status),
            "is_cancellable": TaskStatusTransition.is_cancellable(task.status),
            "is_retryable": TaskStatusTransition.is_retryable(task.status),
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "valid_next_statuses": TaskStatusTransition.VALID_TRANSITIONS.get(task.status, []),
            "timestamps": {
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "queued_at": task.queued_at.isoformat() if task.queued_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "parsing_completed_at": task.parsing_completed_at.isoformat() if task.parsing_completed_at else None,
                "comparing_completed_at": task.comparing_completed_at.isoformat() if task.comparing_completed_at else None,
                "review_completed_at": task.review_completed_at.isoformat() if task.review_completed_at else None,
                "report_completed_at": task.report_completed_at.isoformat() if task.report_completed_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "failed_at": task.failed_at.isoformat() if task.failed_at else None,
                "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
            },
        }

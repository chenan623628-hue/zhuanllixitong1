"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - 事件服务
"""
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.models.task import TaskEvent, TaskEventType, TaskStatus
from app.core.schemas import ErrorCode
from app.core.exceptions import TaskException

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EventService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_event(
        self,
        task_id: str,
        event_type: str,
        event_message: str = "",
        from_status: str | None = None,
        to_status: str | None = None,
        user_id: int | None = None,
        worker_id: str | None = None,
        progress_percent: int | None = None,
        progress_message: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        step_name: str | None = None,
        step_duration_seconds: int | None = None,
        event_details: dict[str, Any] | None = None,
    ) -> TaskEvent:
        event = TaskEvent(
            event_type=event_type,
            event_time=_utcnow(),
            task_id=task_id,
            from_status=from_status,
            to_status=to_status,
            event_message=event_message,
            user_id=user_id,
            worker_id=worker_id,
            progress_percent=progress_percent,
            progress_message=progress_message,
            error_code=error_code,
            error_message=error_message,
            step_name=step_name,
            step_duration_seconds=step_duration_seconds,
        )
        
        if event_details:
            event.set_event_details(event_details)
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        logger.debug(f"Event created: {event.event_type} for task {task_id}")
        
        return event
    
    def get_event(self, event_id: str) -> TaskEvent | None:
        return self.db.query(TaskEvent).filter(
            TaskEvent.event_id == event_id
        ).first()
    
    def get_task_events(
        self,
        task_id: str,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[TaskEvent], int]:
        query = self.db.query(TaskEvent).filter(
            TaskEvent.task_id == task_id
        )
        
        if event_type:
            query = query.filter(TaskEvent.event_type == event_type)
        
        total = query.count()
        
        events = query.order_by(
            desc(TaskEvent.event_time)
        ).offset(offset).limit(limit).all()
        
        return events, total
    
    def get_task_status_history(
        self,
        task_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        status_changes = self.db.query(TaskEvent).filter(
            TaskEvent.task_id == task_id,
            TaskEvent.from_status.isnot(None),
            TaskEvent.to_status.isnot(None),
        ).order_by(TaskEvent.event_time).all()
        
        return [
            {
                "from_status": e.from_status,
                "to_status": e.to_status,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "event_message": e.event_message,
                "user_id": e.user_id,
                "worker_id": e.worker_id,
            }
            for e in status_changes
        ]
    
    def get_task_progress_logs(
        self,
        task_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        progress_events = self.db.query(TaskEvent).filter(
            TaskEvent.task_id == task_id,
            TaskEvent.progress_percent.isnot(None),
        ).order_by(TaskEvent.event_time).all()
        
        return [
            {
                "event_type": e.event_type,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "progress_percent": e.progress_percent,
                "progress_message": e.progress_message,
                "step_name": e.step_name,
                "step_duration_seconds": e.step_duration_seconds,
            }
            for e in progress_events
        ]
    
    def get_task_error_events(
        self,
        task_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        error_events = self.db.query(TaskEvent).filter(
            TaskEvent.task_id == task_id,
            or_(
                TaskEvent.event_type == TaskEventType.TASK_FAILED,
                TaskEvent.event_type == TaskEventType.ERROR_OCCURRED,
                TaskEvent.event_type == TaskEventType.RETRY_FAILED,
                TaskEvent.error_code.isnot(None),
            )
        ).order_by(desc(TaskEvent.event_time)).limit(limit).all()
        
        return [
            {
                "event_type": e.event_type,
                "event_time": e.event_time.isoformat() if e.event_time else None,
                "error_code": e.error_code,
                "error_message": e.error_message,
                "from_status": e.from_status,
                "to_status": e.to_status,
                "event_details": e.get_event_details(),
            }
            for e in error_events
        ]
    
    def get_latest_event(
        self,
        task_id: str,
        event_type: str | None = None,
    ) -> TaskEvent | None:
        query = self.db.query(TaskEvent).filter(
            TaskEvent.task_id == task_id
        )
        
        if event_type:
            query = query.filter(TaskEvent.event_type == event_type)
        
        return query.order_by(desc(TaskEvent.event_time)).first()
    
    def record_task_created(
        self,
        task_id: str,
        user_id: int | None = None,
        task_type: str = "",
        details: dict[str, Any] | None = None,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.TASK_CREATED,
            event_message=f"任务已创建，类型: {task_type}",
            user_id=user_id,
            event_details=details,
        )
    
    def record_task_queued(
        self,
        task_id: str,
        worker_id: str | None = None,
        queue_position: int | None = None,
    ) -> TaskEvent:
        details = {}
        if queue_position is not None:
            details["queue_position"] = queue_position
        
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.TASK_QUEUED,
            event_message=f"任务已入队，位置: {queue_position or 'N/A'}",
            worker_id=worker_id,
            event_details=details,
        )
    
    def record_task_started(
        self,
        task_id: str,
        worker_id: str | None = None,
        from_status: str = TaskStatus.PENDING,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.TASK_STARTED,
            event_message="任务开始执行",
            from_status=from_status,
            to_status=TaskStatus.PARSING,
            worker_id=worker_id,
            progress_percent=10,
            progress_message="开始解析文件",
        )
    
    def record_step_progress(
        self,
        task_id: str,
        step_name: str,
        progress_percent: int,
        progress_message: str,
        worker_id: str | None = None,
        step_duration: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.PROGRESS_UPDATE,
            event_message=progress_message,
            worker_id=worker_id,
            progress_percent=progress_percent,
            progress_message=progress_message,
            step_name=step_name,
            step_duration_seconds=step_duration,
            event_details=details,
        )
    
    def record_error(
        self,
        task_id: str,
        error_code: str,
        error_message: str,
        worker_id: str | None = None,
        from_status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.ERROR_OCCURRED,
            event_message=f"错误: {error_message}",
            worker_id=worker_id,
            from_status=from_status,
            error_code=error_code,
            error_message=error_message,
            event_details=details,
        )
    
    def record_task_failed(
        self,
        task_id: str,
        error_code: str,
        error_message: str,
        worker_id: str | None = None,
        from_status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.TASK_FAILED,
            event_message=f"任务失败: {error_message}",
            worker_id=worker_id,
            from_status=from_status,
            to_status=TaskStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            event_details=details,
        )
    
    def record_retry_attempt(
        self,
        task_id: str,
        retry_count: int,
        worker_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.RETRY_ATTEMPT,
            event_message=f"重试尝试 (第 {retry_count} 次)",
            worker_id=worker_id,
            event_details=details,
        )
    
    def record_task_cancelled(
        self,
        task_id: str,
        reason: str = "",
        user_id: int | None = None,
        from_status: str | None = None,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.TASK_CANCELLED,
            event_message=reason or "任务已取消",
            user_id=user_id,
            from_status=from_status,
            to_status=TaskStatus.CANCELLED,
        )
    
    def record_task_completed(
        self,
        task_id: str,
        worker_id: str | None = None,
        duration_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> TaskEvent:
        return self.create_event(
            task_id=task_id,
            event_type=TaskEventType.TASK_COMPLETED,
            event_message="任务执行完成",
            worker_id=worker_id,
            progress_percent=100,
            progress_message="任务完成",
            step_duration_seconds=duration_seconds,
            event_details=details,
        )

"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - 任务服务
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, update

from app.models.task import (
    Task, TaskEvent, TaskType, TaskStatus, TaskStatusTransition,
    PriorityLevel, TaskEventType, TaskStep
)
from app.models.file import File, FileType
from app.models.user import User
from app.core.schemas import ErrorCode
from app.core.exceptions import TaskException
from app.services.task.state_machine_service import StateMachineService
from app.services.task.event_service import EventService

logger = logging.getLogger(__name__)

DEFAULT_LEASE_DURATION_SECONDS = 300
HEARTBEAT_EXTEND_SECONDS = 120
SYSTEM_ADMIN_ROLE = "system_admin"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class CreateTaskContext:
    task_name: str
    task_type: str
    standard_file_id: str
    patent_file_ids: list[str]
    rule_template_id: str | None = None
    task_description: str | None = None
    priority: int = PriorityLevel.NORMAL
    max_retries: int = 3
    user_id: int | None = None
    created_ip: str | None = None
    created_source: str = "web"
    is_admin: bool = False
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class UpdateProgressContext:
    task_id: str
    progress_percent: int
    progress_message: str
    step_name: str | None = None
    step_duration: int | None = None
    worker_id: str | None = None
    details: dict[str, Any] | None = None


class TaskService:
    def __init__(self, db: Session):
        self.db = db
        self.state_machine = StateMachineService(db)
        self.event_service = EventService(db)
    
    def validate_create_context(self, context: CreateTaskContext) -> None:
        if not context.task_name or not context.task_name.strip():
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message="任务名称不能为空"
            )
        
        if not context.standard_file_id:
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message="必须指定标准文件"
            )
        
        if not context.patent_file_ids:
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message="必须指定至少一个专利文件"
            )
        
        if context.task_type not in [TaskType.ONE_TO_ONE, TaskType.N_TO_ONE]:
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message=f"无效的任务类型: {context.task_type}"
            )
        
        if context.task_type == TaskType.ONE_TO_ONE and len(context.patent_file_ids) != 1:
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message="1:1 任务只能指定一个专利文件"
            )
        
        if context.priority < 1 or context.priority > 15:
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message="优先级必须在 1-15 之间"
            )
    
    def _validate_files(self, context: CreateTaskContext) -> dict[str, File]:
        all_file_ids = [context.standard_file_id] + context.patent_file_ids
        
        files = self.db.query(File).filter(
            File.file_id.in_(all_file_ids),
            File.is_deleted == False
        ).all()
        
        file_map = {f.file_id: f for f in files}
        
        if context.standard_file_id not in file_map:
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message=f"标准文件不存在: {context.standard_file_id}"
            )
        
        standard_file = file_map[context.standard_file_id]
        if standard_file.file_type not in [FileType.STANDARD, FileType.OTHER]:
            raise TaskException(
                code=ErrorCode.TASK_CREATE_FAILED,
                message=f"文件 {context.standard_file_id} 不是标准文件类型"
            )
        
        for patent_file_id in context.patent_file_ids:
            if patent_file_id not in file_map:
                raise TaskException(
                    code=ErrorCode.TASK_CREATE_FAILED,
                    message=f"专利文件不存在: {patent_file_id}"
                )
            patent_file = file_map[patent_file_id]
            if patent_file.file_type not in [FileType.PATENT, FileType.OTHER]:
                raise TaskException(
                    code=ErrorCode.TASK_CREATE_FAILED,
                    message=f"文件 {patent_file_id} 不是专利文件类型"
                )
        
        if not context.is_admin and context.user_id is not None:
            for file_id, f in file_map.items():
                if f.upload_user_id is not None and f.upload_user_id != context.user_id:
                    raise TaskException(
                        code=ErrorCode.PERM_ACCESS_DENIED,
                        message=f"无权使用文件: {file_id}（文件所有者为其他用户）"
                    )
        
        return file_map
    
    def create_task(self, context: CreateTaskContext) -> Task:
        self.validate_create_context(context)
        
        file_map = self._validate_files(context)
        
        task = Task(
            task_name=context.task_name,
            task_description=context.task_description,
            task_type=context.task_type,
            standard_file_id=context.standard_file_id,
            rule_template_id=context.rule_template_id,
            priority=context.priority,
            max_retries=context.max_retries,
            status=TaskStatus.PENDING,
            user_id=context.user_id,
            created_ip=context.created_ip,
            created_source=context.created_source,
            progress_percent=0,
            retry_count=0,
        )
        
        task.set_patent_file_ids(context.patent_file_ids)
        
        if context.tags:
            task.set_tags(context.tags)
        
        if context.metadata:
            task.set_metadata(context.metadata)
        
        self.db.add(task)
        self.db.flush()
        
        self.event_service.record_task_created(
            task_id=task.task_id,
            user_id=context.user_id,
            task_type=context.task_type,
            details={
                "standard_file_id": context.standard_file_id,
                "patent_file_count": len(context.patent_file_ids),
                "priority": context.priority,
            }
        )
        
        self.db.commit()
        self.db.refresh(task)
        
        logger.info(f"Task created: {task.task_id} - {context.task_name}")
        
        return task
    
    def get_task(self, task_id: str) -> Task | None:
        return self.db.query(Task).filter(
            Task.task_id == task_id
        ).first()
    
    def get_task_or_raise(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if not task:
            raise TaskException(
                code=ErrorCode.TASK_NOT_FOUND,
                message=f"任务不存在: {task_id}"
            )
        return task
    
    def get_user_tasks(
        self,
        user_id: int | None,
        status: str | None = None,
        task_type: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
        is_admin: bool = False,
    ) -> tuple[list[Task], int]:
        query = self.db.query(Task)
        
        if not is_admin and user_id is not None:
            query = query.filter(Task.user_id == user_id)
        
        if status:
            if "," in status:
                statuses = [s.strip() for s in status.split(",")]
                query = query.filter(Task.status.in_(statuses))
            else:
                query = query.filter(Task.status == status)
        
        if task_type:
            query = query.filter(Task.task_type == task_type)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Task.task_name.like(search_term),
                    Task.task_id.like(search_term),
                )
            )
        
        total = query.count()
        
        tasks = query.order_by(
            desc(Task.priority),
            desc(Task.created_at)
        ).offset(offset).limit(limit).all()
        
        return tasks, total
    
    def get_task_detail(self, task_id: str, include_events: bool = True, events_limit: int = 50) -> dict[str, Any]:
        task = self.get_task_or_raise(task_id)
        
        result = {
            "task": task.to_dict(),
            "status_summary": self.state_machine.get_task_status_summary(task),
        }
        
        if include_events:
            events, total = self.event_service.get_task_events(
                task_id=task_id,
                limit=events_limit
            )
            result["events"] = {
                "items": [e.to_dict() for e in events],
                "total": total,
                "limit": events_limit,
            }
            result["status_history"] = self.event_service.get_task_status_history(task_id, limit=events_limit)
            result["error_events"] = self.event_service.get_task_error_events(task_id)
        
        return result
    
    def cancel_task(
        self,
        task_id: str,
        user_id: int | None = None,
        is_admin: bool = False,
        reason: str = "",
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        if not is_admin and task.user_id != user_id:
            raise TaskException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="无权取消此任务"
            )
        
        self.state_machine.cancel_task(
            task=task,
            reason=reason or "用户手动取消",
            user_id=user_id,
        )
        
        logger.info(f"Task cancelled: {task_id} by user {user_id}")
        
        return task
    
    def retry_task(
        self,
        task_id: str,
        user_id: int | None = None,
        is_admin: bool = False,
        worker_id: str | None = None,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        if not is_admin and task.user_id != user_id:
            raise TaskException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="无权重试此任务"
            )
        
        task.worker_id = None
        task.lease_acquired_at = None
        task.lease_expires_at = None
        task.lease_updated_at = None
        self.db.flush()
        
        self.state_machine.retry_task(
            task=task,
            user_id=user_id,
            worker_id=worker_id,
        )
        
        logger.info(f"Task retried: {task_id} by user {user_id}")
        
        return task
    
    def batch_cancel_tasks(
        self,
        task_ids: list[str],
        user_id: int | None = None,
        is_admin: bool = False,
        reason: str = "",
    ) -> dict[str, Any]:
        success_count = 0
        failed_count = 0
        errors: list[dict[str, Any]] = []
        
        for task_id in task_ids:
            try:
                self.cancel_task(task_id, user_id, is_admin, reason)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "task_id": task_id,
                    "error": str(e),
                })
        
        return {
            "total": len(task_ids),
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
        }
    
    def batch_retry_tasks(
        self,
        task_ids: list[str],
        user_id: int | None = None,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        success_count = 0
        failed_count = 0
        errors: list[dict[str, Any]] = []
        
        for task_id in task_ids:
            try:
                self.retry_task(task_id, user_id, is_admin)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "task_id": task_id,
                    "error": str(e),
                })
        
        return {
            "total": len(task_ids),
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
        }
    
    def get_task_statistics(
        self,
        user_id: int | None = None,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        query = self.db.query(Task)
        
        if not is_admin and user_id is not None:
            query = query.filter(Task.user_id == user_id)
        
        total = query.count()
        
        pending = query.filter(Task.status == TaskStatus.PENDING).count()
        parsing = query.filter(Task.status == TaskStatus.PARSING).count()
        comparing = query.filter(Task.status == TaskStatus.COMPARING).count()
        review_pending = query.filter(Task.status == TaskStatus.REVIEW_PENDING).count()
        reviewed = query.filter(Task.status == TaskStatus.REVIEWED).count()
        report_ready = query.filter(Task.status == TaskStatus.REPORT_READY).count()
        archived = query.filter(Task.status == TaskStatus.ARCHIVED).count()
        failed = query.filter(Task.status == TaskStatus.FAILED).count()
        cancelled = query.filter(Task.status == TaskStatus.CANCELLED).count()
        
        running = parsing + comparing
        waiting = review_pending + reviewed + report_ready
        completed = archived
        final = failed + cancelled + archived
        
        return {
            "total": total,
            "by_status": {
                TaskStatus.PENDING: pending,
                TaskStatus.PARSING: parsing,
                TaskStatus.COMPARING: comparing,
                TaskStatus.REVIEW_PENDING: review_pending,
                TaskStatus.REVIEWED: reviewed,
                TaskStatus.REPORT_READY: report_ready,
                TaskStatus.ARCHIVED: archived,
                TaskStatus.FAILED: failed,
                TaskStatus.CANCELLED: cancelled,
            },
            "summary": {
                "running": running,
                "waiting": waiting,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "final": final,
            }
        }
    
    def get_queued_tasks(
        self,
        limit: int = 100,
        priority_threshold: int | None = None,
    ) -> list[Task]:
        query = self.db.query(Task).filter(
            Task.status == TaskStatus.PENDING,
            Task.is_active == True,
        )
        
        if priority_threshold is not None:
            query = query.filter(Task.priority >= priority_threshold)
        
        return query.order_by(
            desc(Task.priority),
            Task.created_at
        ).limit(limit).all()
    
    def reclaim_expired_leases(self, lease_duration_seconds: int | None = None) -> int:
        if lease_duration_seconds is None:
            lease_duration_seconds = DEFAULT_LEASE_DURATION_SECONDS
        
        now = _utcnow()
        
        expired_tasks = self.db.query(Task).filter(
            Task.status == TaskStatus.PENDING,
            Task.worker_id.isnot(None),
            Task.lease_expires_at.isnot(None),
            Task.lease_expires_at <= now,
        ).all()
        
        reclaimed = 0
        for task in expired_tasks:
            old_worker_id = task.worker_id
            
            task.worker_id = None
            task.lease_acquired_at = None
            task.lease_expires_at = None
            task.lease_updated_at = None
            
            self.event_service.record_step_progress(
                task_id=task.task_id,
                step_name="lease_reclaim",
                progress_percent=0,
                progress_message=f"租约已过期，释放任务。原 Worker: {old_worker_id}",
                details={
                    "previous_worker_id": old_worker_id,
                    "reclaimed_at": now.isoformat(),
                }
            )
            
            reclaimed += 1
            logger.warning(f"Reclaimed expired lease for task {task.task_id} from worker {old_worker_id}")
        
        self.db.commit()
        return reclaimed
    
    def claim_task(
        self,
        worker_id: str,
        worker_version: str | None = None,
        lease_duration_seconds: int | None = None,
    ) -> Task | None:
        if lease_duration_seconds is None:
            lease_duration_seconds = DEFAULT_LEASE_DURATION_SECONDS
        
        self.reclaim_expired_leases()
        self.db.flush()
        
        candidate_task = self.db.query(Task).filter(
            Task.status == TaskStatus.PENDING,
            Task.is_active == True,
            Task.worker_id.is_(None),
        ).order_by(
            desc(Task.priority),
            Task.created_at
        ).first()
        
        if not candidate_task:
            return None
        
        now = _utcnow()
        expires_at = now + timedelta(seconds=lease_duration_seconds)
        
        stmt = update(Task).where(
            Task.id == candidate_task.id,
            Task.worker_id.is_(None),
        ).values(
            worker_id=worker_id,
            worker_version=worker_version,
            queued_at=now,
            lease_acquired_at=now,
            lease_expires_at=expires_at,
            lease_updated_at=now,
        ).execution_options(synchronize_session="fetch")
        
        result = self.db.execute(stmt)
        rows_updated = result.rowcount
        self.db.commit()
        
        if rows_updated == 0:
            logger.info(f"Task {candidate_task.task_id} was claimed by another worker concurrently")
            return None
        
        self.db.refresh(candidate_task)
        
        self.event_service.record_task_queued(
            task_id=candidate_task.task_id,
            worker_id=worker_id,
        )
        
        logger.info(f"Task {candidate_task.task_id} claimed by worker {worker_id}")
        
        return candidate_task
    
    def heartbeat(
        self,
        task_id: str,
        worker_id: str,
        extend_seconds: int | None = None,
    ) -> bool:
        if extend_seconds is None:
            extend_seconds = HEARTBEAT_EXTEND_SECONDS
        
        task = self.db.query(Task).filter(
            Task.task_id == task_id,
            Task.worker_id == worker_id,
        ).first()
        
        if not task:
            return False
        
        now = _utcnow()
        
        if task.lease_expires_at and task.lease_expires_at < now:
            return False
        
        new_expires = now + timedelta(seconds=extend_seconds)
        task.lease_updated_at = now
        task.lease_expires_at = new_expires
        
        self.db.commit()
        
        logger.debug(f"Heartbeat received for task {task_id} from worker {worker_id}")
        
        return True
    
    def start_task(
        self,
        task_id: str,
        worker_id: str,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        self.state_machine.transition(
            task=task,
            to_status=TaskStatus.PARSING,
            event_message="任务开始执行，进入解析阶段",
            worker_id=worker_id,
            progress_percent=10,
            progress_message="正在解析文件...",
        )
        
        logger.info(f"Task {task_id} started by worker {worker_id}")
        
        return task
    
    def move_to_comparing(
        self,
        task_id: str,
        worker_id: str,
        details: dict[str, Any] | None = None,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        self.state_machine.transition(
            task=task,
            to_status=TaskStatus.COMPARING,
            event_message="解析完成，进入比对阶段",
            worker_id=worker_id,
            progress_percent=30,
            progress_message="正在进行比对...",
            event_details=details,
        )
        
        logger.info(f"Task {task_id} moved to comparing by worker {worker_id}")
        
        return task
    
    def move_to_report_ready(
        self,
        task_id: str,
        worker_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        self.state_machine.transition(
            task=task,
            to_status=TaskStatus.REPORT_READY,
            event_message="报告生成完成，等待归档",
            worker_id=worker_id,
            progress_percent=95,
            progress_message="报告已就绪",
            event_details=details,
        )
        
        logger.info(f"Task {task_id} moved to report ready")
        
        return task
    
    def complete_task(
        self,
        task_id: str,
        worker_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        self.state_machine.transition(
            task=task,
            to_status=TaskStatus.ARCHIVED,
            event_message="任务执行完成，已归档",
            worker_id=worker_id,
            progress_percent=100,
            progress_message="任务完成",
            event_details=details,
        )
        
        task.worker_id = None
        task.lease_acquired_at = None
        task.lease_expires_at = None
        task.lease_updated_at = None
        
        self.db.commit()
        
        logger.info(f"Task {task_id} completed by worker {worker_id}")
        
        return task
    
    def fail_task(
        self,
        task_id: str,
        worker_id: str,
        error_code: str,
        error_message: str,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        self.state_machine.mark_as_failed(
            task=task,
            error_code=error_code,
            error_message=error_message,
            worker_id=worker_id,
        )
        
        task.worker_id = None
        task.lease_acquired_at = None
        task.lease_expires_at = None
        task.lease_updated_at = None
        
        self.db.commit()
        
        logger.warning(f"Task {task_id} failed by worker {worker_id}: {error_message}")
        
        return task
    
    def update_progress(
        self,
        context: UpdateProgressContext,
    ) -> TaskEvent:
        task = self.get_task_or_raise(context.task_id)
        
        return self.state_machine.update_progress(
            task=task,
            progress_percent=context.progress_percent,
            progress_message=context.progress_message,
            step_name=context.step_name,
            step_duration=context.step_duration,
            worker_id=context.worker_id,
        )
    
    def move_to_review(
        self,
        task_id: str,
        worker_id: str,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        self.state_machine.transition(
            task=task,
            to_status=TaskStatus.REVIEW_PENDING,
            event_message="比对完成，等待人工校验",
            worker_id=worker_id,
            progress_percent=70,
            progress_message="等待人工校验",
        )
        
        logger.info(f"Task {task_id} moved to review pending")
        
        return task
    
    def complete_review(
        self,
        task_id: str,
        user_id: int | None = None,
        review_result: str | None = None,
        review_comment: str | None = None,
    ) -> Task:
        task = self.get_task_or_raise(task_id)
        
        details = {}
        if review_result:
            details["review_result"] = review_result
        if review_comment:
            details["review_comment"] = review_comment
        
        self.state_machine.transition(
            task=task,
            to_status=TaskStatus.REVIEWED,
            event_message=review_comment or "人工校验完成",
            user_id=user_id,
            progress_percent=85,
            progress_message="人工校验完成",
            event_details=details,
        )
        
        logger.info(f"Task {task_id} review completed by user {user_id}")
        
        return task
    
    def get_lease_status(self, task_id: str) -> dict[str, Any] | None:
        task = self.get_task(task_id)
        if not task:
            return None
        
        now = _utcnow()
        is_expired = False
        seconds_remaining = None
        
        if task.lease_expires_at:
            is_expired = task.lease_expires_at <= now
            if not is_expired:
                seconds_remaining = int((task.lease_expires_at - now).total_seconds())
        
        return {
            "task_id": task.task_id,
            "worker_id": task.worker_id,
            "lease_acquired_at": task.lease_acquired_at.isoformat() if task.lease_acquired_at else None,
            "lease_expires_at": task.lease_expires_at.isoformat() if task.lease_expires_at else None,
            "lease_updated_at": task.lease_updated_at.isoformat() if task.lease_updated_at else None,
            "is_expired": is_expired,
            "seconds_remaining": seconds_remaining,
        }

"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - 数据模型
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from enum import Enum

from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TaskType:
    ONE_TO_ONE = "1:1"
    N_TO_ONE = "N:1"


class TaskStatus:
    PENDING = "pending"
    PARSING = "parsing"
    COMPARING = "comparing"
    REVIEW_PENDING = "review_pending"
    REVIEWED = "reviewed"
    REPORT_READY = "report_ready"
    ARCHIVED = "archived"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatusTransition:
    VALID_TRANSITIONS = {
        TaskStatus.PENDING: [TaskStatus.PARSING, TaskStatus.CANCELLED, TaskStatus.FAILED],
        TaskStatus.PARSING: [TaskStatus.COMPARING, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.COMPARING: [TaskStatus.REVIEW_PENDING, TaskStatus.FAILED, TaskStatus.CANCELLED],
        TaskStatus.REVIEW_PENDING: [TaskStatus.REVIEWED, TaskStatus.CANCELLED, TaskStatus.FAILED],
        TaskStatus.REVIEWED: [TaskStatus.REPORT_READY, TaskStatus.FAILED],
        TaskStatus.REPORT_READY: [TaskStatus.ARCHIVED],
        TaskStatus.ARCHIVED: [],
        TaskStatus.FAILED: [TaskStatus.PENDING],
        TaskStatus.CANCELLED: [TaskStatus.PENDING],
    }
    
    FINAL_STATUSES = [TaskStatus.ARCHIVED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    RUNNING_STATUSES = [TaskStatus.PARSING, TaskStatus.COMPARING]
    QUEUE_STATUSES = [TaskStatus.PENDING]
    WAITING_STATUSES = [TaskStatus.REVIEW_PENDING, TaskStatus.REPORT_READY]
    
    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        if from_status not in cls.VALID_TRANSITIONS:
            return False
        return to_status in cls.VALID_TRANSITIONS[from_status]
    
    @classmethod
    def is_final(cls, status: str) -> bool:
        return status in cls.FINAL_STATUSES
    
    @classmethod
    def is_running(cls, status: str) -> bool:
        return status in cls.RUNNING_STATUSES
    
    @classmethod
    def is_cancellable(cls, status: str) -> bool:
        return status in [TaskStatus.PENDING, TaskStatus.PARSING, TaskStatus.COMPARING]
    
    @classmethod
    def is_retryable(cls, status: str) -> bool:
        return status in [TaskStatus.FAILED, TaskStatus.CANCELLED]


class PriorityLevel:
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 15


class Task(BaseModel):
    __tablename__ = "tasks"
    __table_args__ = (
        {"comment": "比对任务主表"},
    )

    task_id = Column(String(64), unique=True, nullable=False, index=True, comment="任务唯一标识 UUID")
    
    task_type = Column(String(16), nullable=False, default=TaskType.ONE_TO_ONE, comment="任务类型：1:1/N:1")
    task_name = Column(String(256), nullable=False, comment="任务名称")
    task_description = Column(Text, nullable=True, comment="任务描述")
    
    status = Column(String(32), nullable=False, default=TaskStatus.PENDING, index=True, comment="任务状态")
    previous_status = Column(String(32), nullable=True, comment="上一状态（用于状态回滚追踪）")
    
    priority = Column(Integer, nullable=False, default=PriorityLevel.NORMAL, index=True, comment="优先级：1=低/5=正常/10=高/15=紧急")
    
    patent_file_id = Column(String(64), nullable=True, comment="专利文件ID（1:1场景）")
    patent_file_ids = Column(Text, nullable=True, comment="专利文件ID列表 JSON（N:1场景）")
    standard_file_id = Column(String(64), nullable=False, index=True, comment="标准文件ID")
    
    rule_template_id = Column(String(64), nullable=True, index=True, comment="使用的规则模板ID")
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="创建用户ID")
    created_ip = Column(String(64), nullable=True, comment="创建IP地址")
    created_source = Column(String(64), nullable=True, default="web", comment="创建来源：web/api")
    
    queued_at = Column(DateTime, nullable=True, comment="入队时间")
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    parsing_completed_at = Column(DateTime, nullable=True, comment="解析完成时间")
    comparing_completed_at = Column(DateTime, nullable=True, comment="比对完成时间")
    review_completed_at = Column(DateTime, nullable=True, comment="人工校验完成时间")
    report_completed_at = Column(DateTime, nullable=True, comment="报告生成完成时间")
    completed_at = Column(DateTime, nullable=True, comment="最终完成时间")
    failed_at = Column(DateTime, nullable=True, comment="失败时间")
    cancelled_at = Column(DateTime, nullable=True, comment="取消时间")
    
    estimated_duration_seconds = Column(Integer, nullable=True, comment="预估耗时（秒）")
    actual_duration_seconds = Column(Integer, nullable=True, comment="实际耗时（秒）")
    
    progress_percent = Column(Integer, default=0, nullable=False, comment="进度百分比 0-100")
    progress_message = Column(String(512), nullable=True, comment="进度描述消息")
    
    retry_count = Column(Integer, default=0, nullable=False, comment="重试次数")
    max_retries = Column(Integer, default=3, nullable=False, comment="最大重试次数")
    
    error_code = Column(String(64), nullable=True, comment="错误码")
    error_message = Column(Text, nullable=True, comment="错误信息")
    error_traceback = Column(Text, nullable=True, comment="错误堆栈（仅开发环境）")
    
    worker_id = Column(String(64), nullable=True, index=True, comment="执行的 Worker 实例ID")
    worker_version = Column(String(32), nullable=True, comment="Worker 版本号")
    
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="是否启用")
    is_archived = Column(Boolean, default=False, nullable=False, index=True, comment="是否已归档")
    
    task_metadata = Column("metadata", Text, nullable=True, comment="扩展元数据（JSON）")
    tags = Column(Text, nullable=True, comment="标签列表（JSON数组）")
    
    created_user = relationship("User", backref="tasks")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.task_id:
            self.task_id = uuid.uuid4().hex
    
    def get_patent_file_ids(self) -> list[str]:
        if self.patent_file_ids:
            try:
                return json.loads(self.patent_file_ids)
            except json.JSONDecodeError:
                return []
        if self.patent_file_id:
            return [self.patent_file_id]
        return []
    
    def set_patent_file_ids(self, file_ids: list[str]):
        if len(file_ids) == 1:
            self.patent_file_id = file_ids[0]
            self.patent_file_ids = None
            self.task_type = TaskType.ONE_TO_ONE
        else:
            self.patent_file_id = None
            self.patent_file_ids = json.dumps(file_ids)
            self.task_type = TaskType.N_TO_ONE
    
    def get_metadata(self) -> dict[str, Any]:
        if self.task_metadata:
            try:
                return json.loads(self.task_metadata)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, data: dict[str, Any]):
        self.task_metadata = json.dumps(data, ensure_ascii=False)
    
    def get_tags(self) -> list[str]:
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags: list[str]):
        self.tags = json.dumps(tags, ensure_ascii=False)
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["task_id"] = self.task_id
        data["task_type"] = self.task_type
        data["task_name"] = self.task_name
        data["task_description"] = self.task_description
        data["status"] = self.status
        data["previous_status"] = self.previous_status
        data["priority"] = self.priority
        data["patent_file_id"] = self.patent_file_id
        data["patent_file_ids"] = self.get_patent_file_ids()
        data["standard_file_id"] = self.standard_file_id
        data["rule_template_id"] = self.rule_template_id
        data["user_id"] = self.user_id
        data["created_ip"] = self.created_ip
        data["created_source"] = self.created_source
        data["queued_at"] = self.queued_at.isoformat() if self.queued_at else None
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        data["failed_at"] = self.failed_at.isoformat() if self.failed_at else None
        data["cancelled_at"] = self.cancelled_at.isoformat() if self.cancelled_at else None
        data["estimated_duration_seconds"] = self.estimated_duration_seconds
        data["actual_duration_seconds"] = self.actual_duration_seconds
        data["progress_percent"] = self.progress_percent
        data["progress_message"] = self.progress_message
        data["retry_count"] = self.retry_count
        data["max_retries"] = self.max_retries
        data["error_code"] = self.error_code
        data["error_message"] = self.error_message
        data["is_active"] = self.is_active
        data["is_archived"] = self.is_archived
        data["metadata"] = self.get_metadata()
        data["tags"] = self.get_tags()
        return data
    
    def __repr__(self) -> str:
        return f"<Task id={self.id} task_id={self.task_id} status={self.status}>"


class TaskEvent(BaseModel):
    __tablename__ = "task_events"
    __table_args__ = (
        {"comment": "任务事件日志表"},
    )

    event_id = Column(String(64), unique=True, nullable=False, index=True, comment="事件唯一标识")
    event_type = Column(String(64), nullable=False, index=True, comment="事件类型")
    event_time = Column(DateTime, nullable=False, default=_utcnow, index=True, comment="事件时间")
    
    task_id = Column(String(64), nullable=False, index=True, comment="关联任务ID")
    
    from_status = Column(String(32), nullable=True, comment="转移前状态")
    to_status = Column(String(32), nullable=True, comment="转移后状态")
    
    event_message = Column(String(1024), nullable=True, comment="事件描述消息")
    event_details = Column(Text, nullable=True, comment="事件详情（JSON）")
    
    progress_percent = Column(Integer, nullable=True, comment="进度百分比（如果是进度事件）")
    progress_message = Column(String(512), nullable=True, comment="进度消息")
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="触发事件的用户ID")
    worker_id = Column(String(64), nullable=True, index=True, comment="触发事件的Worker ID")
    
    error_code = Column(String(64), nullable=True, index=True, comment="错误码（错误事件）")
    error_message = Column(Text, nullable=True, comment="错误信息")
    
    step_name = Column(String(128), nullable=True, index=True, comment="执行步骤名称")
    step_duration_seconds = Column(Integer, nullable=True, comment="步骤耗时（秒）")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
    
    def get_event_details(self) -> dict[str, Any]:
        if self.event_details:
            try:
                return json.loads(self.event_details)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_event_details(self, data: dict[str, Any]):
        self.event_details = json.dumps(data, ensure_ascii=False)
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["event_id"] = self.event_id
        data["event_type"] = self.event_type
        data["event_time"] = self.event_time.isoformat() if self.event_time else None
        data["task_id"] = self.task_id
        data["from_status"] = self.from_status
        data["to_status"] = self.to_status
        data["event_message"] = self.event_message
        data["event_details"] = self.get_event_details()
        data["progress_percent"] = self.progress_percent
        data["progress_message"] = self.progress_message
        data["user_id"] = self.user_id
        data["worker_id"] = self.worker_id
        data["error_code"] = self.error_code
        data["error_message"] = self.error_message
        data["step_name"] = self.step_name
        data["step_duration_seconds"] = self.step_duration_seconds
        return data
    
    def __repr__(self) -> str:
        return f"<TaskEvent id={self.id} event_type={self.event_type} task_id={self.task_id}>"


class TaskEventType:
    TASK_CREATED = "task.created"
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_PARSED = "task.parsed"
    TASK_COMPARED = "task.compared"
    TASK_REVIEW_STARTED = "task.review_started"
    TASK_REVIEW_COMPLETED = "task.review_completed"
    TASK_REPORT_GENERATED = "task.report_generated"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_RETRIED = "task.retried"
    TASK_ARCHIVED = "task.archived"
    
    STATUS_CHANGE = "status.change"
    PROGRESS_UPDATE = "progress.update"
    STEP_COMPLETED = "step.completed"
    ERROR_OCCURRED = "error.occurred"
    RETRY_ATTEMPT = "retry.attempt"
    RETRY_SUCCESS = "retry.success"
    RETRY_FAILED = "retry.failed"


class TaskStep:
    FILE_PREPARATION = "file_preparation"
    PDF_PARSING = "pdf_parsing"
    DOCX_PARSING = "docx_parsing"
    TEXT_EXTRACTION = "text_extraction"
    FEATURE_EXTRACTION = "feature_extraction"
    TERM_MAPPING = "term_mapping"
    CLAIM_PARSING = "claim_parsing"
    CLAIM_COMPARISON = "claim_comparison"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    EVIDENCE_VERIFICATION = "evidence_verification"
    JUDGMENT = "judgment"
    RESULT_AGGREGATION = "result_aggregation"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"


class StateMachine:
    @staticmethod
    def get_event_for_transition(from_status: str, to_status: str) -> str | None:
        transition_map = {
            (TaskStatus.PENDING, TaskStatus.PARSING): TaskEventType.TASK_STARTED,
            (TaskStatus.PARSING, TaskStatus.COMPARING): TaskEventType.TASK_PARSED,
            (TaskStatus.COMPARING, TaskStatus.REVIEW_PENDING): TaskEventType.TASK_COMPARED,
            (TaskStatus.REVIEW_PENDING, TaskStatus.REVIEWED): TaskEventType.TASK_REVIEW_COMPLETED,
            (TaskStatus.REVIEWED, TaskStatus.REPORT_READY): TaskEventType.TASK_REPORT_GENERATED,
            (TaskStatus.REPORT_READY, TaskStatus.ARCHIVED): TaskEventType.TASK_ARCHIVED,
        }
        return transition_map.get((from_status, to_status))

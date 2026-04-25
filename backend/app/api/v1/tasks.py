"""
专利-标准比对系统 V1.0
M05 任务管理与编排模块 - API 路由
"""
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Header,
    Request,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.schemas import ApiResponse, ErrorCode
from app.core.responses import create_success_response, create_error_response
from app.core.auth import (
    get_current_user,
    CurrentUser,
    require_permission,
)
from app.core.exceptions import TaskException
from app.db import get_db
from app.services.task import (
    TaskService,
    CreateTaskContext,
    UpdateProgressContext,
    EventService,
    StateMachineService,
)
from app.models.task import (
    Task, TaskEvent, TaskType, TaskStatus, TaskStatusTransition,
    PriorityLevel, TaskEventType
)

router = APIRouter(prefix="/tasks", tags=["任务管理"])


class TaskItemResponse(BaseModel):
    task_id: str
    task_name: str
    task_type: str
    task_description: str | None
    status: str
    previous_status: str | None
    priority: int
    
    standard_file_id: str
    patent_file_id: str | None
    patent_file_ids: list[str]
    rule_template_id: str | None
    
    user_id: int | None
    created_ip: str | None
    created_source: str
    
    progress_percent: int
    progress_message: str | None
    
    retry_count: int
    max_retries: int
    error_code: str | None
    error_message: str | None
    
    worker_id: str | None
    is_active: bool
    is_archived: bool
    
    created_at: str | None
    queued_at: str | None
    started_at: str | None
    completed_at: str | None
    failed_at: str | None
    cancelled_at: str | None
    
    estimated_duration_seconds: int | None
    actual_duration_seconds: int | None


class TaskListResponse(BaseModel):
    tasks: list[TaskItemResponse]
    total: int
    offset: int
    limit: int


class CreateTaskRequest(BaseModel):
    task_name: str = Field(..., min_length=1, max_length=256, description="任务名称")
    task_type: str = Field(default=TaskType.ONE_TO_ONE, description="任务类型：1:1/N:1")
    standard_file_id: str = Field(..., description="标准文件ID")
    patent_file_ids: list[str] = Field(..., min_length=1, description="专利文件ID列表")
    rule_template_id: str | None = Field(default=None, description="规则模板ID")
    task_description: str | None = Field(default=None, max_length=1000, description="任务描述")
    priority: int = Field(default=PriorityLevel.NORMAL, ge=1, le=15, description="优先级")
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    tags: list[str] | None = Field(default=None, description="标签列表")
    metadata: dict[str, Any] | None = Field(default=None, description="扩展元数据")


class CreateTaskResponse(BaseModel):
    task_id: str
    task_name: str
    status: str
    priority: int


class TaskDetailResponse(BaseModel):
    task: TaskItemResponse
    status_summary: dict[str, Any]
    events: dict[str, Any] | None = None
    status_history: list[dict[str, Any]] | None = None
    error_events: list[dict[str, Any]] | None = None


class BatchActionRequest(BaseModel):
    task_ids: list[str] = Field(..., min_length=1, description="任务ID列表")
    reason: str | None = Field(default=None, description="原因说明")


class BatchActionResponse(BaseModel):
    total: int
    success: int
    failed: int
    errors: list[dict[str, Any]]


class TaskStatisticsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    summary: dict[str, int]


class EventItemResponse(BaseModel):
    event_id: str
    event_type: str
    event_time: str
    task_id: str
    from_status: str | None
    to_status: str | None
    event_message: str | None
    progress_percent: int | None
    progress_message: str | None
    user_id: int | None
    worker_id: str | None
    error_code: str | None
    error_message: str | None
    step_name: str | None
    step_duration_seconds: int | None
    event_details: dict[str, Any]


class EventListResponse(BaseModel):
    events: list[EventItemResponse]
    total: int
    offset: int
    limit: int


class UpdateProgressRequest(BaseModel):
    progress_percent: int = Field(..., ge=0, le=100, description="进度百分比")
    progress_message: str | None = Field(default=None, description="进度消息")
    step_name: str | None = Field(default=None, description="步骤名称")
    step_duration: int | None = Field(default=None, description="步骤耗时(秒)")
    details: dict[str, Any] | None = Field(default=None, description="扩展详情")


class CompleteReviewRequest(BaseModel):
    review_result: str | None = Field(default=None, description="校验结果")
    review_comment: str | None = Field(default=None, description="校验评论")


def _task_to_response(task: Task) -> TaskItemResponse:
    return TaskItemResponse(
        task_id=task.task_id,
        task_name=task.task_name,
        task_type=task.task_type,
        task_description=task.task_description,
        status=task.status,
        previous_status=task.previous_status,
        priority=task.priority,
        standard_file_id=task.standard_file_id,
        patent_file_id=task.patent_file_id,
        patent_file_ids=task.get_patent_file_ids(),
        rule_template_id=task.rule_template_id,
        user_id=task.user_id,
        created_ip=task.created_ip,
        created_source=task.created_source,
        progress_percent=task.progress_percent,
        progress_message=task.progress_message,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        error_code=task.error_code,
        error_message=task.error_message,
        worker_id=task.worker_id,
        is_active=task.is_active,
        is_archived=task.is_archived,
        created_at=task.created_at.isoformat() if task.created_at else None,
        queued_at=task.queued_at.isoformat() if task.queued_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        failed_at=task.failed_at.isoformat() if task.failed_at else None,
        cancelled_at=task.cancelled_at.isoformat() if task.cancelled_at else None,
        estimated_duration_seconds=task.estimated_duration_seconds,
        actual_duration_seconds=task.actual_duration_seconds,
    )


def _event_to_response(event: TaskEvent) -> EventItemResponse:
    return EventItemResponse(
        event_id=event.event_id,
        event_type=event.event_type,
        event_time=event.event_time.isoformat() if event.event_time else None,
        task_id=event.task_id,
        from_status=event.from_status,
        to_status=event.to_status,
        event_message=event.event_message,
        progress_percent=event.progress_percent,
        progress_message=event.progress_message,
        user_id=event.user_id,
        worker_id=event.worker_id,
        error_code=event.error_code,
        error_message=event.error_message,
        step_name=event.step_name,
        step_duration_seconds=event.step_duration_seconds,
        event_details=event.get_event_details(),
    )


def _get_client_ip(request: Request, x_forwarded_for: str | None) -> str | None:
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("", response_model=ApiResponse)
async def create_task(
    request: Request,
    data: CreateTaskRequest,
    x_forwarded_for: str | None = Header(default=None),
    current_user: CurrentUser = Depends(require_permission("task:create")),
    db: Session = Depends(get_db),
):
    """
    创建比对任务
    需要权限: task:create
    """
    client_ip = _get_client_ip(request, x_forwarded_for)
    
    context = CreateTaskContext(
        task_name=data.task_name,
        task_type=data.task_type,
        standard_file_id=data.standard_file_id,
        patent_file_ids=data.patent_file_ids,
        rule_template_id=data.rule_template_id,
        task_description=data.task_description,
        priority=data.priority,
        max_retries=data.max_retries,
        user_id=current_user.id,
        created_ip=client_ip,
        created_source="web",
        tags=data.tags,
        metadata=data.metadata,
    )
    
    task_service = TaskService(db)
    task = task_service.create_task(context)
    
    result = CreateTaskResponse(
        task_id=task.task_id,
        task_name=task.task_name,
        status=task.status,
        priority=task.priority,
    )
    
    return create_success_response(
        data=result.model_dump(),
        message="任务创建成功"
    )


@router.get("", response_model=ApiResponse)
async def get_tasks(
    status: str | None = Query(default=None, description="状态过滤，多个用逗号分隔"),
    task_type: str | None = Query(default=None, description="任务类型过滤"),
    search: str | None = Query(default=None, description="搜索关键词"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    limit: int = Query(default=50, ge=1, le=200, description="每页数量"),
    current_user: CurrentUser = Depends(require_permission("task:view")),
    db: Session = Depends(get_db),
):
    """
    获取任务列表
    需要权限: task:view
    """
    task_service = TaskService(db)
    
    tasks, total = task_service.get_user_tasks(
        user_id=current_user.id,
        status=status,
        task_type=task_type,
        search=search,
        offset=offset,
        limit=limit,
        is_admin=current_user.is_admin,
    )
    
    response = TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=total,
        offset=offset,
        limit=limit,
    )
    
    return create_success_response(
        data=response.model_dump(),
        message="获取任务列表成功"
    )


@router.get("/statistics", response_model=ApiResponse)
async def get_task_statistics(
    current_user: CurrentUser = Depends(require_permission("task:view")),
    db: Session = Depends(get_db),
):
    """
    获取任务统计
    需要权限: task:view
    """
    task_service = TaskService(db)
    
    stats = task_service.get_task_statistics(
        user_id=current_user.id,
        is_admin=current_user.is_admin,
    )
    
    return create_success_response(
        data=stats,
        message="获取任务统计成功"
    )


@router.get("/{task_id}", response_model=ApiResponse)
async def get_task_detail(
    task_id: str,
    include_events: bool = Query(default=True, description="是否包含事件日志"),
    events_limit: int = Query(default=50, ge=1, le=200, description="事件日志数量"),
    current_user: CurrentUser = Depends(require_permission("task:view")),
    db: Session = Depends(get_db),
):
    """
    获取任务详情
    需要权限: task:view
    """
    task_service = TaskService(db)
    task = task_service.get_task_or_raise(task_id)
    
    if task.user_id != current_user.id and not current_user.is_admin:
        raise TaskException(
            code=ErrorCode.PERM_ACCESS_DENIED,
            message="无权访问此任务"
        )
    
    detail = task_service.get_task_detail(
        task_id=task_id,
        include_events=include_events,
        events_limit=events_limit,
    )
    
    detail["task"] = _task_to_response(task).model_dump()
    
    return create_success_response(
        data=detail,
        message="获取任务详情成功"
    )


@router.post("/{task_id}/cancel", response_model=ApiResponse)
async def cancel_task(
    task_id: str,
    reason: str | None = Query(default=None, description="取消原因"),
    current_user: CurrentUser = Depends(require_permission("task:delete")),
    db: Session = Depends(get_db),
):
    """
    取消任务
    需要权限: task:delete
    """
    task_service = TaskService(db)
    task = task_service.cancel_task(
        task_id=task_id,
        user_id=current_user.id,
        is_admin=current_user.is_admin,
        reason=reason,
    )
    
    return create_success_response(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
        },
        message="任务取消成功"
    )


@router.post("/{task_id}/retry", response_model=ApiResponse)
async def retry_task(
    task_id: str,
    current_user: CurrentUser = Depends(require_permission("task:execute")),
    db: Session = Depends(get_db),
):
    """
    重试任务
    需要权限: task:execute
    """
    task_service = TaskService(db)
    task = task_service.retry_task(
        task_id=task_id,
        user_id=current_user.id,
        is_admin=current_user.is_admin,
    )
    
    return create_success_response(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "retry_count": task.retry_count,
        },
        message="任务重试成功"
    )


@router.post("/batch/cancel", response_model=ApiResponse)
async def batch_cancel_tasks(
    data: BatchActionRequest,
    current_user: CurrentUser = Depends(require_permission("task:delete")),
    db: Session = Depends(get_db),
):
    """
    批量取消任务
    需要权限: task:delete
    """
    task_service = TaskService(db)
    
    result = task_service.batch_cancel_tasks(
        task_ids=data.task_ids,
        user_id=current_user.id,
        is_admin=current_user.is_admin,
        reason=data.reason,
    )
    
    response = BatchActionResponse(**result)
    
    return create_success_response(
        data=response.model_dump(),
        message=f"批量取消完成：成功 {result['success']} 个，失败 {result['failed']} 个"
    )


@router.post("/batch/retry", response_model=ApiResponse)
async def batch_retry_tasks(
    data: BatchActionRequest,
    current_user: CurrentUser = Depends(require_permission("task:execute")),
    db: Session = Depends(get_db),
):
    """
    批量重试任务
    需要权限: task:execute
    """
    task_service = TaskService(db)
    
    result = task_service.batch_retry_tasks(
        task_ids=data.task_ids,
        user_id=current_user.id,
        is_admin=current_user.is_admin,
    )
    
    response = BatchActionResponse(**result)
    
    return create_success_response(
        data=response.model_dump(),
        message=f"批量重试完成：成功 {result['success']} 个，失败 {result['failed']} 个"
    )


@router.get("/{task_id}/events", response_model=ApiResponse)
async def get_task_events(
    task_id: str,
    event_type: str | None = Query(default=None, description="事件类型过滤"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    limit: int = Query(default=50, ge=1, le=200, description="每页数量"),
    current_user: CurrentUser = Depends(require_permission("task:view")),
    db: Session = Depends(get_db),
):
    """
    获取任务事件日志
    需要权限: task:view
    """
    task_service = TaskService(db)
    task = task_service.get_task_or_raise(task_id)
    
    if task.user_id != current_user.id and not current_user.is_admin:
        raise TaskException(
            code=ErrorCode.PERM_ACCESS_DENIED,
            message="无权访问此任务"
        )
    
    event_service = EventService(db)
    events, total = event_service.get_task_events(
        task_id=task_id,
        event_type=event_type,
        offset=offset,
        limit=limit,
    )
    
    response = EventListResponse(
        events=[_event_to_response(e) for e in events],
        total=total,
        offset=offset,
        limit=limit,
    )
    
    return create_success_response(
        data=response.model_dump(),
        message="获取事件日志成功"
    )


@router.post("/{task_id}/review/complete", response_model=ApiResponse)
async def complete_task_review(
    task_id: str,
    data: CompleteReviewRequest,
    current_user: CurrentUser = Depends(require_permission("task:execute")),
    db: Session = Depends(get_db),
):
    """
    完成人工校验
    需要权限: task:execute
    """
    task_service = TaskService(db)
    task = task_service.get_task_or_raise(task_id)
    
    if task.user_id != current_user.id and not current_user.is_admin:
        raise TaskException(
            code=ErrorCode.PERM_ACCESS_DENIED,
            message="无权操作此任务"
        )
    
    task = task_service.complete_review(
        task_id=task_id,
        user_id=current_user.id,
        review_result=data.review_result,
        review_comment=data.review_comment,
    )
    
    return create_success_response(
        data={
            "task_id": task.task_id,
            "status": task.status,
            "review_completed_at": task.review_completed_at.isoformat() if task.review_completed_at else None,
        },
        message="人工校验完成"
    )


@router.get("/config/statuses", response_model=ApiResponse)
async def get_task_status_config(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    获取任务状态配置
    """
    return create_success_response(
        data={
            "statuses": {
                TaskStatus.PENDING: {"name": "待执行", "color": "#f59e0b", "group": "pending"},
                TaskStatus.PARSING: {"name": "解析中", "color": "#3b82f6", "group": "running"},
                TaskStatus.COMPARING: {"name": "比对中", "color": "#3b82f6", "group": "running"},
                TaskStatus.REVIEW_PENDING: {"name": "待校验", "color": "#ec4899", "group": "waiting"},
                TaskStatus.REVIEWED: {"name": "已校验", "color": "#8b5cf6", "group": "waiting"},
                TaskStatus.REPORT_READY: {"name": "报告就绪", "color": "#10b981", "group": "waiting"},
                TaskStatus.ARCHIVED: {"name": "已完成", "color": "#10b981", "group": "completed"},
                TaskStatus.FAILED: {"name": "失败", "color": "#ef4444", "group": "failed"},
                TaskStatus.CANCELLED: {"name": "已取消", "color": "#6b7280", "group": "cancelled"},
            },
            "valid_transitions": TaskStatusTransition.VALID_TRANSITIONS,
            "final_statuses": TaskStatusTransition.FINAL_STATUSES,
            "running_statuses": TaskStatusTransition.RUNNING_STATUSES,
            "queue_statuses": TaskStatusTransition.QUEUE_STATUSES,
            "waiting_statuses": TaskStatusTransition.WAITING_STATUSES,
        },
        message="获取任务状态配置成功"
    )


@router.get("/config/types", response_model=ApiResponse)
async def get_task_type_config(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    获取任务类型配置
    """
    return create_success_response(
        data={
            "types": {
                TaskType.ONE_TO_ONE: {
                    "name": "1:1 比对",
                    "description": "单个专利 vs 单个标准",
                    "min_patents": 1,
                    "max_patents": 1,
                },
                TaskType.N_TO_ONE: {
                    "name": "N:1 比对",
                    "description": "多个专利 vs 单个标准",
                    "min_patents": 2,
                    "max_patents": 10,
                },
            }
        },
        message="获取任务类型配置成功"
    )

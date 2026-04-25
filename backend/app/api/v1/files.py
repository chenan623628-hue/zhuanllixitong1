"""
专利-标准比对系统 V1.0
M04 文件上传与安全网关模块 - API 路由
"""
import os
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    Request,
    UploadFile,
    File,
    Form,
    Query,
    Header,
    HTTPException,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.schemas import ApiResponse, ErrorCode
from app.core.responses import create_success_response, create_error_response
from app.core.auth import (
    get_current_user,
    CurrentUser,
    require_permission,
)
from app.core.exceptions import FileException
from app.db import get_db
from app.services.file import (
    FileService,
    UploadContext,
    SecurityService,
    ExcelService,
)
from app.models.file import (
    FileType,
    FileStatus,
    ScanStatus,
    AllowedFileTypes,
)

router = APIRouter(prefix="/files", tags=["文件上传"])


class FileInfoResponse(BaseModel):
    file_id: str
    original_name: str
    stored_name: str
    file_type: str
    file_category: str | None
    file_size: int
    page_count: int | None
    file_hash: str | None
    status: str
    scan_status: str | None
    upload_user_id: int | None
    upload_ip: str | None
    task_id: str | None
    created_at: str | None
    is_active: bool


class UploadResult(BaseModel):
    file_id: str
    original_name: str
    file_size: int
    file_type: str
    status: str
    scan_status: str


class BatchUploadResult(BaseModel):
    total: int
    success: int
    failed: int
    files: list[UploadResult]
    errors: list[dict[str, Any]]


class FileListResponse(BaseModel):
    files: list[FileInfoResponse]
    total: int
    offset: int
    limit: int


class ExcelPreviewResponse(BaseModel):
    valid: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    headers: list[str]
    sample_data: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


class SecurityEventItem(BaseModel):
    event_id: str
    event_type: str
    event_time: str
    file_id: str | None
    file_name: str | None
    severity: str
    check_type: str | None
    check_result: str | None
    block_reason: str | None
    risk_score: int | None
    is_blocked: bool


class SecurityEventsResponse(BaseModel):
    events: list[SecurityEventItem]
    total: int
    offset: int
    limit: int


def _get_client_ip(request: Request, x_forwarded_for: str | None) -> str | None:
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _file_to_response(file_record) -> FileInfoResponse:
    return FileInfoResponse(
        file_id=file_record.file_id,
        original_name=file_record.original_name,
        stored_name=file_record.stored_name,
        file_type=file_record.file_type,
        file_category=file_record.file_category,
        file_size=file_record.file_size,
        page_count=file_record.page_count,
        file_hash=file_record.file_hash,
        status=file_record.status,
        scan_status=file_record.scan_status,
        upload_user_id=file_record.upload_user_id,
        upload_ip=file_record.upload_ip,
        task_id=file_record.task_id,
        created_at=file_record.created_at.isoformat() if file_record.created_at else None,
        is_active=file_record.is_active,
    )


@router.post("/upload", response_model=ApiResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(..., description="上传的文件"),
    file_type: str = Form(default=FileType.OTHER, description="文件类型：patent/standard/excel_import/other"),
    task_id: str | None = Form(default=None, description="关联任务ID"),
    user_agent: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    current_user: CurrentUser = Depends(require_permission("file:upload")),
    db: Session = Depends(get_db),
):
    """
    单文件上传
    需要权限: file:upload
    """
    client_ip = _get_client_ip(request, x_forwarded_for)
    
    upload_context = UploadContext(
        user_id=current_user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        file_type=file_type,
        upload_source="web",
        task_id=task_id,
    )
    
    file_service = FileService(db)
    security_service = SecurityService(db)
    
    file_obj = file.file
    original_name = file.filename or "unnamed"
    
    security_check = security_service.quick_validate(
        filename=original_name,
        file_size=0,
        content_type=file.content_type,
    )
    
    if not security_check.allowed:
        raise FileException(
            code=ErrorCode.FILE_INVALID_TYPE,
            message=security_check.reasons[0] if security_check.reasons else "文件验证失败"
        )
    
    file_record = file_service.store_file(
        file_obj=file_obj,
        original_name=original_name,
        upload_context=upload_context,
    )
    
    scan_result = security_service.run_security_scan(file_record.file_id)
    
    result = UploadResult(
        file_id=file_record.file_id,
        original_name=file_record.original_name,
        file_size=file_record.file_size,
        file_type=file_record.file_type,
        status=file_record.status,
        scan_status=file_record.scan_status,
    )
    
    return create_success_response(
        data=result.model_dump(),
        message="文件上传成功" if scan_result.passed else "文件上传成功，安全扫描中"
    )


@router.post("/upload/batch", response_model=ApiResponse)
async def upload_files_batch(
    request: Request,
    files: list[UploadFile] = File(..., description="上传的文件列表"),
    file_type: str = Form(default=FileType.OTHER, description="文件类型"),
    task_id: str | None = Form(default=None, description="关联任务ID"),
    user_agent: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    current_user: CurrentUser = Depends(require_permission("file:upload")),
    db: Session = Depends(get_db),
):
    """
    批量文件上传
    需要权限: file:upload
    限制: 最多同时上传 10 个文件
    """
    max_files = settings.MAX_FILES_PER_TASK
    if len(files) > max_files:
        raise FileException(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"最多同时上传 {max_files} 个文件"
        )
    
    client_ip = _get_client_ip(request, x_forwarded_for)
    
    file_service = FileService(db)
    security_service = SecurityService(db)
    
    success_count = 0
    failed_count = 0
    results: list[UploadResult] = []
    errors: list[dict[str, Any]] = []
    
    for index, file in enumerate(files):
        try:
            upload_context = UploadContext(
                user_id=current_user.id,
                ip_address=client_ip,
                user_agent=user_agent,
                file_type=file_type,
                upload_source="web",
                task_id=task_id,
            )
            
            file_obj = file.file
            original_name = file.filename or f"file_{index}"
            
            file_record = file_service.store_file(
                file_obj=file_obj,
                original_name=original_name,
                upload_context=upload_context,
            )
            
            security_service.run_security_scan(file_record.file_id)
            
            results.append(UploadResult(
                file_id=file_record.file_id,
                original_name=file_record.original_name,
                file_size=file_record.file_size,
                file_type=file_record.file_type,
                status=file_record.status,
                scan_status=file_record.scan_status,
            ))
            success_count += 1
            
        except Exception as e:
            failed_count += 1
            errors.append({
                "index": index,
                "filename": file.filename,
                "error": str(e),
            })
    
    result = BatchUploadResult(
        total=len(files),
        success=success_count,
        failed=failed_count,
        files=results,
        errors=errors,
    )
    
    return create_success_response(
        data=result.model_dump(),
        message=f"批量上传完成：成功 {success_count} 个，失败 {failed_count} 个"
    )


@router.get("", response_model=ApiResponse)
async def get_files(
    file_type: str | None = Query(default=None, description="文件类型过滤"),
    status: str | None = Query(default=None, description="状态过滤"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    limit: int = Query(default=50, ge=1, le=200, description="每页数量"),
    current_user: CurrentUser = Depends(require_permission("file:view")),
    db: Session = Depends(get_db),
):
    """
    获取文件列表
    需要权限: file:view
    """
    file_service = FileService(db)
    
    files, total = file_service.get_user_files(
        user_id=current_user.id,
        file_type=file_type,
        status=status,
        offset=offset,
        limit=limit,
    )
    
    response = FileListResponse(
        files=[_file_to_response(f) for f in files],
        total=total,
        offset=offset,
        limit=limit,
    )
    
    return create_success_response(
        data=response.model_dump(),
        message="获取文件列表成功"
    )


@router.get("/{file_id}", response_model=ApiResponse)
async def get_file_detail(
    file_id: str,
    current_user: CurrentUser = Depends(require_permission("file:view")),
    db: Session = Depends(get_db),
):
    """
    获取文件详情
    需要权限: file:view
    """
    file_service = FileService(db)
    file_record = file_service.get_file_by_id_or_raise(file_id)
    
    if file_record.upload_user_id != current_user.id and not current_user.is_admin:
        raise FileException(
            code=ErrorCode.PERM_ACCESS_DENIED,
            message="无权访问此文件"
        )
    
    return create_success_response(
        data=_file_to_response(file_record).model_dump(),
        message="获取文件详情成功"
    )


@router.delete("/{file_id}", response_model=ApiResponse)
async def delete_file(
    file_id: str,
    current_user: CurrentUser = Depends(require_permission("file:delete")),
    db: Session = Depends(get_db),
):
    """
    删除文件
    需要权限: file:delete
    """
    file_service = FileService(db)
    file_record = file_service.get_file_by_id_or_raise(file_id)
    
    if file_record.upload_user_id != current_user.id and not current_user.is_admin:
        raise FileException(
            code=ErrorCode.PERM_ACCESS_DENIED,
            message="无权删除此文件"
        )
    
    file_service.mark_file_deleted(file_id, current_user.id)
    
    return create_success_response(
        data={"file_id": file_id, "deleted": True},
        message="文件删除成功"
    )


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: CurrentUser = Depends(require_permission("file:download")),
    db: Session = Depends(get_db),
):
    """
    下载文件
    需要权限: file:download
    """
    file_service = FileService(db)
    file_record = file_service.get_file_by_id_or_raise(file_id)
    
    if file_record.upload_user_id != current_user.id and not current_user.is_admin:
        raise FileException(
            code=ErrorCode.PERM_ACCESS_DENIED,
            message="无权下载此文件"
        )
    
    if file_record.status == FileStatus.BLOCKED:
        raise FileException(
            code=ErrorCode.FILE_UPLOAD_FAILED,
            message="文件被安全策略阻断，无法下载"
        )
    
    full_path = file_service.get_file_full_path(file_record)
    
    if not os.path.exists(full_path):
        raise FileException(
            code=ErrorCode.FILE_NOT_FOUND,
            message="文件不存在"
        )
    
    return FileResponse(
        path=full_path,
        filename=file_record.original_name,
        media_type=file_record.mime_type or "application/octet-stream",
    )


@router.post("/excel/preview", response_model=ApiResponse)
async def preview_excel(
    request: Request,
    file: UploadFile = File(..., description="Excel 文件"),
    user_agent: str | None = Header(default=None),
    x_forwarded_for: str | None = Header(default=None),
    current_user: CurrentUser = Depends(require_permission("file:upload")),
    db: Session = Depends(get_db),
):
    """
    Excel 文件预检
    需要权限: file:upload
    """
    import tempfile
    
    excel_service = ExcelService(db)
    file_service = FileService(db)
    
    content = await file.read()
    file_size = len(content)
    
    max_size = settings.MAX_FILE_SIZE
    if file_size > max_size:
        raise FileException(
            code=ErrorCode.FILE_TOO_LARGE,
            message=f"文件大小超过限制（最大 {max_size // (1024 * 1024)}MB）"
        )
    
    original_name = file.filename or "upload.xlsx"
    ext = os.path.splitext(original_name)[1].lower()
    
    if ext not in [".xlsx", ".xls"]:
        raise FileException(
            code=ErrorCode.FILE_INVALID_TYPE,
            message="仅支持 Excel 文件（.xlsx/.xls）"
        )
    
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        preview = excel_service.preview_excel(tmp_path)
        
        response = ExcelPreviewResponse(
            valid=preview.valid,
            total_rows=preview.total_rows,
            valid_rows=preview.valid_rows,
            invalid_rows=preview.invalid_rows,
            headers=preview.headers,
            sample_data=preview.sample_data,
            errors=[
                {
                    "row": e.row,
                    "column": e.column,
                    "column_name": e.column_name,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                }
                for e in preview.errors
            ],
            warnings=preview.warnings,
        )
        
        return create_success_response(
            data=response.model_dump(),
            message="Excel 预检完成"
        )
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/security/events", response_model=ApiResponse)
async def get_security_events(
    event_type: str | None = Query(default=None, description="事件类型过滤"),
    severity: str | None = Query(default=None, description="严重程度过滤"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    limit: int = Query(default=50, ge=1, le=200, description="每页数量"),
    current_user: CurrentUser = Depends(require_permission("file:view")),
    db: Session = Depends(get_db),
):
    """
    获取安全事件列表
    需要权限: file:view
    """
    security_service = SecurityService(db)
    
    events, total = security_service.get_security_events(
        user_id=current_user.id if not current_user.is_admin else None,
        event_type=event_type,
        severity=severity,
        offset=offset,
        limit=limit,
    )
    
    response = SecurityEventsResponse(
        events=[
            SecurityEventItem(
                event_id=e.event_id,
                event_type=e.event_type,
                event_time=e.event_time.isoformat() if e.event_time else None,
                file_id=e.file_id,
                file_name=e.file_name,
                severity=e.severity,
                check_type=e.check_type,
                check_result=e.check_result,
                block_reason=e.block_reason,
                risk_score=e.risk_score,
                is_blocked=e.is_blocked,
            )
            for e in events
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
    
    return create_success_response(
        data=response.model_dump(),
        message="获取安全事件成功"
    )


@router.get("/config/limits", response_model=ApiResponse)
async def get_upload_limits(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    获取上传限制配置
    """
    return create_success_response(
        data={
            "max_file_size_mb": settings.MAX_FILE_SIZE // (1024 * 1024),
            "max_pages": settings.MAX_PAGES,
            "max_files_per_task": settings.MAX_FILES_PER_TASK,
            "max_excel_rows": 50,
            "allowed_extensions": AllowedFileTypes.get_allowed_extensions(),
            "allowed_mime_types": AllowedFileTypes.get_allowed_mime_types(),
        },
        message="获取上传限制成功"
    )

"""
专利-标准比对系统 V1.0
M04 文件上传与安全网关模块 - 文件上传服务
"""
import hashlib
import logging
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import unquote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import FileException
from app.core.schemas import ErrorCode
from app.models.file import (
    File, FileType, FileStatus, ScanStatus,
    UploadSecurityEvent, SecurityEventType, AllowedFileTypes
)

logger = logging.getLogger(__name__)


@dataclass
class FileValidationResult:
    valid: bool
    error_code: int | None = None
    error_message: str | None = None
    file_category: str | None = None
    file_extension: str | None = None
    mime_type: str | None = None


@dataclass
class UploadContext:
    user_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    file_type: str = FileType.OTHER
    upload_source: str = "web"
    task_id: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sanitize_filename(filename: str) -> str:
    filename = unquote(filename)
    
    name, ext = os.path.splitext(filename)
    
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    
    name = name.strip()
    if not name:
        name = "unnamed"
    
    max_name_length = 100
    if len(name) > max_name_length:
        name = name[:max_name_length]
        name = name.strip()
    
    ext = ext.lower()
    
    return f"{name}{ext}"


def _get_file_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _guess_mime_type(filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def _calculate_hash(file_obj: BinaryIO, algorithm: str = "sha256") -> str:
    hash_obj = hashlib.new(algorithm)
    file_obj.seek(0)
    while chunk := file_obj.read(8192):
        hash_obj.update(chunk)
    file_obj.seek(0)
    return hash_obj.hexdigest()


class FileService:
    def __init__(self, db: Session):
        self.db = db
        self._ensure_upload_dirs()
    
    def _ensure_upload_dirs(self) -> None:
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        for subdir in ["patents", "standards", "imports", "temp"]:
            (upload_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    def validate_file(
        self,
        filename: str,
        file_size: int,
        content_type: str | None = None,
    ) -> FileValidationResult:
        extension = _get_file_extension(filename)
        
        if not AllowedFileTypes.is_allowed_extension(extension):
            return FileValidationResult(
                valid=False,
                error_code=ErrorCode.FILE_INVALID_TYPE,
                error_message=f"不支持的文件格式 '{extension}'，仅支持: {', '.join(AllowedFileTypes.get_allowed_extensions())}"
            )
        
        if file_size > settings.MAX_FILE_SIZE:
            max_mb = settings.MAX_FILE_SIZE // (1024 * 1024)
            return FileValidationResult(
                valid=False,
                error_code=ErrorCode.FILE_TOO_LARGE,
                error_message=f"文件大小超过限制（最大 {max_mb}MB）"
            )
        
        mime_type = content_type or _guess_mime_type(filename)
        file_category = AllowedFileTypes.get_file_category(extension)
        
        return FileValidationResult(
            valid=True,
            file_category=file_category,
            file_extension=extension,
            mime_type=mime_type,
        )
    
    def validate_page_count(self, page_count: int | None) -> FileValidationResult:
        if page_count is None:
            return FileValidationResult(valid=True)
        
        if page_count > settings.MAX_PAGES:
            return FileValidationResult(
                valid=False,
                error_code=ErrorCode.FILE_TOO_MANY_PAGES,
                error_message=f"文件页数超过限制（最大 {settings.MAX_PAGES} 页）"
            )
        
        return FileValidationResult(valid=True)
    
    def _get_upload_subdir(self, file_type: str) -> str:
        if file_type == FileType.PATENT:
            return "patents"
        elif file_type == FileType.STANDARD:
            return "standards"
        elif file_type == FileType.EXCEL_IMPORT:
            return "imports"
        return "temp"
    
    def _generate_stored_name(
        self,
        original_name: str,
        file_extension: str,
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = uuid.uuid4().hex[:8]
        name = os.path.splitext(original_name)[0]
        name = re.sub(r'[^\w\-_.]', '_', name)
        name = name[:50]
        
        return f"{name}_{timestamp}_{random_suffix}{file_extension}"
    
    def store_file(
        self,
        file_obj: BinaryIO,
        original_name: str,
        upload_context: UploadContext,
    ) -> File:
        sanitized_name = _sanitize_filename(original_name)
        
        file_obj.seek(0, 2)
        file_size = file_obj.tell()
        file_obj.seek(0)
        
        validation = self.validate_file(sanitized_name, file_size)
        if not validation.valid:
            self._log_security_event(
                event_type=SecurityEventType.FILE_TYPE_CHECK,
                file_name=sanitized_name,
                file_size=file_size,
                user_id=upload_context.user_id,
                ip_address=upload_context.ip_address,
                user_agent=upload_context.user_agent,
                severity="warning",
                check_type="file_type",
                check_result="failed",
                block_reason=validation.error_message,
                is_blocked=True,
            )
            raise FileException(
                code=validation.error_code or ErrorCode.FILE_INVALID_TYPE,
                message=validation.error_message
            )
        
        file_hash = _calculate_hash(file_obj)
        
        existing_file = self.db.query(File).filter(
            File.file_hash == file_hash,
            File.is_deleted == False
        ).first()
        
        if existing_file:
            self._log_security_event(
                event_type=SecurityEventType.FILE_HASH_DUPLICATE,
                file_id=existing_file.file_id,
                file_name=sanitized_name,
                file_size=file_size,
                file_hash=file_hash,
                user_id=upload_context.user_id,
                ip_address=upload_context.ip_address,
                user_agent=upload_context.user_agent,
                severity="info",
                check_type="hash",
                check_result="passed",
            )
            return existing_file
        
        subdir = self._get_upload_subdir(upload_context.file_type)
        stored_name = self._generate_stored_name(sanitized_name, validation.file_extension or "")
        
        relative_path = os.path.join(subdir, stored_name)
        full_path = os.path.join(settings.UPLOAD_DIR, relative_path)
        
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "wb") as f:
            file_obj.seek(0)
            while chunk := file_obj.read(8192):
                f.write(chunk)
        
        file_record = File(
            original_name=sanitized_name,
            stored_name=stored_name,
            file_path=relative_path,
            file_type=upload_context.file_type,
            file_category=validation.file_category,
            file_size=file_size,
            file_hash=file_hash,
            mime_type=validation.mime_type,
            file_extension=validation.file_extension,
            status=FileStatus.UPLOADED,
            scan_status=ScanStatus.PENDING,
            upload_user_id=upload_context.user_id,
            upload_ip=upload_context.ip_address,
            upload_source=upload_context.upload_source,
            task_id=upload_context.task_id,
        )
        
        self.db.add(file_record)
        self.db.commit()
        self.db.refresh(file_record)
        
        self._log_security_event(
            event_type=SecurityEventType.FILE_UPLOAD_COMPLETE,
            file_id=file_record.file_id,
            file_name=sanitized_name,
            file_size=file_size,
            file_hash=file_hash,
            user_id=upload_context.user_id,
            ip_address=upload_context.ip_address,
            user_agent=upload_context.user_agent,
            severity="info",
            check_type="upload",
            check_result="passed",
        )
        
        logger.info(f"File uploaded: {file_record.file_id} - {sanitized_name} ({file_size} bytes)")
        
        return file_record
    
    def get_file_by_id(self, file_id: str) -> File | None:
        return self.db.query(File).filter(
            File.file_id == file_id,
            File.is_deleted == False
        ).first()
    
    def get_file_by_id_or_raise(self, file_id: str) -> File:
        file_record = self.get_file_by_id(file_id)
        if not file_record:
            raise FileException(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"文件不存在: {file_id}"
            )
        return file_record
    
    def get_user_files(
        self,
        user_id: int,
        file_type: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[File], int]:
        query = self.db.query(File).filter(
            File.upload_user_id == user_id,
            File.is_deleted == False
        )
        
        if file_type:
            query = query.filter(File.file_type == file_type)
        
        if status:
            query = query.filter(File.status == status)
        
        total = query.count()
        
        files = query.order_by(File.created_at.desc()).offset(offset).limit(limit).all()
        
        return files, total
    
    def update_file_status(
        self,
        file_id: str,
        status: str,
        scan_status: str | None = None,
        page_count: int | None = None,
    ) -> File:
        file_record = self.get_file_by_id_or_raise(file_id)
        
        file_record.status = status
        if scan_status:
            file_record.scan_status = scan_status
        if page_count is not None:
            file_record.page_count = page_count
        
        self.db.commit()
        self.db.refresh(file_record)
        
        return file_record
    
    def mark_file_deleted(self, file_id: str, user_id: int | None = None) -> bool:
        file_record = self.get_file_by_id_or_raise(file_id)
        
        if user_id is not None and file_record.upload_user_id != user_id:
            raise FileException(
                code=ErrorCode.PERM_ACCESS_DENIED,
                message="无权删除此文件"
            )
        
        file_record.is_deleted = True
        file_record.deleted_at = _utcnow()
        file_record.status = FileStatus.FAILED
        
        self.db.commit()
        
        self._log_security_event(
            event_type=SecurityEventType.FILE_DELETED,
            file_id=file_record.file_id,
            file_name=file_record.original_name,
            file_size=file_record.file_size,
            file_hash=file_record.file_hash,
            user_id=user_id,
            severity="info",
        )
        
        logger.info(f"File deleted: {file_id}")
        
        return True
    
    def get_file_full_path(self, file_record: File) -> str:
        return os.path.join(settings.UPLOAD_DIR, file_record.file_path)
    
    def _log_security_event(
        self,
        event_type: str,
        file_id: str | None = None,
        file_name: str | None = None,
        file_size: int | None = None,
        file_hash: str | None = None,
        user_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        severity: str = "info",
        check_type: str | None = None,
        check_result: str | None = None,
        check_details: dict[str, Any] | None = None,
        block_reason: str | None = None,
        risk_score: int | None = None,
        action_taken: str | None = None,
        is_blocked: bool = False,
    ) -> UploadSecurityEvent:
        import json
        event = UploadSecurityEvent(
            event_type=event_type,
            event_time=_utcnow(),
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            file_hash=file_hash,
            upload_user_id=user_id,
            upload_ip=ip_address,
            user_agent=user_agent,
            severity=severity,
            check_type=check_type,
            check_result=check_result,
            check_details=json.dumps(check_details) if check_details else None,
            block_reason=block_reason,
            risk_score=risk_score,
            action_taken=action_taken,
            is_blocked=is_blocked,
        )
        
        self.db.add(event)
        self.db.commit()
        
        return event

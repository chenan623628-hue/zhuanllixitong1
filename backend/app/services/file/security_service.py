"""
专利-标准比对系统 V1.0
M04 文件上传与安全网关模块 - 安全检测服务
"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import FileException
from app.core.schemas import ErrorCode
from app.models.file import (
    File, FileStatus, ScanStatus,
    UploadSecurityEvent, SecurityEventType
)
from app.services.file.file_service import FileService, _utcnow

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    passed: bool
    scan_status: str
    risk_score: int
    details: dict[str, Any]
    block_reason: str | None = None


@dataclass
class SecurityCheckResult:
    allowed: bool
    risk_score: int
    reasons: list[str]
    details: dict[str, Any]


class SecurityService:
    def __init__(self, db: Session):
        self.db = db
        self.file_service = FileService(db)
    
    def run_security_scan(self, file_id: str) -> ScanResult:
        file_record = self.file_service.get_file_by_id_or_raise(file_id)
        
        self._log_event(
            file_id=file_id,
            event_type=SecurityEventType.FILE_VIRUS_SCAN,
            check_type="virus",
            check_result="scanning",
            severity="info",
        )
        
        file_record.scan_status = ScanStatus.SCANNING
        self.db.commit()
        
        type_check = self._check_file_type(file_record)
        if not type_check.allowed:
            return self._create_blocked_result(
                file_record,
                "virus",
                type_check.reasons[0] if type_check.reasons else "文件类型检测失败",
                type_check.risk_score,
                type_check.details,
            )
        
        size_check = self._check_file_size(file_record)
        if not size_check.allowed:
            return self._create_blocked_result(
                file_record,
                "size",
                size_check.reasons[0] if size_check.reasons else "文件大小检测失败",
                size_check.risk_score,
                size_check.details,
            )
        
        content_check = self._check_content(file_record)
        if not content_check.allowed:
            return self._create_blocked_result(
                file_record,
                "content",
                content_check.reasons[0] if content_check.reasons else "内容检测失败",
                content_check.risk_score,
                content_check.details,
            )
        
        final_risk_score = max(
            type_check.risk_score,
            size_check.risk_score,
            content_check.risk_score,
        )
        
        scan_details = {
            "file_type_check": type_check.details,
            "file_size_check": size_check.details,
            "content_check": content_check.details,
            "total_risk_score": final_risk_score,
        }
        
        if final_risk_score >= 70:
            return self._create_blocked_result(
                file_record,
                "content",
                f"文件风险评分过高: {final_risk_score}",
                final_risk_score,
                scan_details,
            )
        
        file_record.scan_status = ScanStatus.PASSED
        file_record.status = FileStatus.READY
        file_record.scan_result = json.dumps(scan_details, ensure_ascii=False)
        file_record.scan_time = _utcnow()
        self.db.commit()
        
        self._log_event(
            file_id=file_id,
            event_type=SecurityEventType.FILE_VIRUS_SCAN,
            check_type="virus",
            check_result="passed",
            severity="info",
            risk_score=final_risk_score,
            details=scan_details,
        )
        
        logger.info(f"Security scan passed for file {file_id}, risk score: {final_risk_score}")
        
        return ScanResult(
            passed=True,
            scan_status=ScanStatus.PASSED,
            risk_score=final_risk_score,
            details=scan_details,
        )
    
    def _check_file_type(self, file_record: File) -> SecurityCheckResult:
        from app.models.file import AllowedFileTypes
        
        details = {
            "extension": file_record.file_extension,
            "mime_type": file_record.mime_type,
            "expected_extensions": AllowedFileTypes.get_allowed_extensions(),
        }
        
        if file_record.file_extension:
            if not AllowedFileTypes.is_allowed_extension(file_record.file_extension):
                return SecurityCheckResult(
                    allowed=False,
                    risk_score=100,
                    reasons=[f"不允许的文件扩展名: {file_record.file_extension}"],
                    details=details,
                )
        
        if file_record.mime_type:
            if not AllowedFileTypes.is_allowed_mime_type(file_record.mime_type):
                return SecurityCheckResult(
                    allowed=False,
                    risk_score=80,
                    reasons=[f"不允许的 MIME 类型: {file_record.mime_type}"],
                    details=details,
                )
        
        extension_risk = self._get_extension_risk(file_record.file_extension)
        
        details["extension_risk"] = extension_risk
        
        return SecurityCheckResult(
            allowed=True,
            risk_score=extension_risk,
            reasons=[],
            details=details,
        )
    
    def _check_file_size(self, file_record: File) -> SecurityCheckResult:
        file_size = file_record.file_size or 0
        max_size = settings.MAX_FILE_SIZE
        
        details = {
            "file_size": file_size,
            "max_size": max_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "max_size_mb": round(max_size / (1024 * 1024), 2),
        }
        
        if file_size > max_size:
            return SecurityCheckResult(
                allowed=False,
                risk_score=100,
                reasons=[f"文件大小超过限制: {details['size_mb']}MB > {details['max_size_mb']}MB"],
                details=details,
            )
        
        size_ratio = file_size / max_size
        risk_score = int(size_ratio * 30)
        
        details["size_ratio"] = size_ratio
        
        return SecurityCheckResult(
            allowed=True,
            risk_score=risk_score,
            reasons=[],
            details=details,
        )
    
    def _check_content(self, file_record: File) -> SecurityCheckResult:
        details = {
            "file_id": file_record.file_id,
            "file_category": file_record.file_category,
            "scanner": "basic_pattern_check",
            "patterns_checked": [],
            "matches_found": 0,
        }
        
        risk_score = 0
        reasons = []
        
        patterns = [
            {"name": "executable_extensions", "risk": 90, "check": self._check_executable_extension},
            {"name": "script_patterns", "risk": 80, "check": self._check_script_patterns},
            {"name": "suspicious_headers", "risk": 70, "check": self._check_suspicious_headers},
        ]
        
        for pattern in patterns:
            details["patterns_checked"].append(pattern["name"])
            result = pattern["check"](file_record)
            if result:
                risk_score = max(risk_score, pattern["risk"])
                reasons.append(f"检测到 {pattern['name']}")
                details["matches_found"] += 1
        
        details["risk_score"] = risk_score
        details["reasons"] = reasons
        
        return SecurityCheckResult(
            allowed=risk_score < 70,
            risk_score=risk_score,
            reasons=reasons,
            details=details,
        )
    
    def _get_extension_risk(self, extension: str | None) -> int:
        if not extension:
            return 10
        
        ext = extension.lower()
        
        high_risk = [".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js", ".jar"]
        medium_risk = [".zip", ".rar", ".7z", ".tar", ".gz"]
        low_risk = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"]
        
        if ext in high_risk:
            return 90
        elif ext in medium_risk:
            return 40
        elif ext in low_risk:
            return 5
        return 20
    
    def _check_executable_extension(self, file_record: File) -> bool:
        if not file_record.file_extension:
            return False
        
        exec_extensions = [".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs"]
        return file_record.file_extension.lower() in exec_extensions
    
    def _check_script_patterns(self, file_record: File) -> bool:
        return False
    
    def _check_suspicious_headers(self, file_record: File) -> bool:
        return False
    
    def _create_blocked_result(
        self,
        file_record: File,
        check_type: str,
        reason: str,
        risk_score: int,
        details: dict[str, Any],
    ) -> ScanResult:
        file_record.scan_status = ScanStatus.BLOCKED
        file_record.status = FileStatus.BLOCKED
        file_record.scan_result = json.dumps(details, ensure_ascii=False)
        file_record.scan_time = _utcnow()
        self.db.commit()
        
        self._log_event(
            file_id=file_record.file_id,
            event_type=SecurityEventType.FILE_BLOCKED,
            check_type=check_type,
            check_result="blocked",
            severity="high",
            block_reason=reason,
            risk_score=risk_score,
            details=details,
            is_blocked=True,
        )
        
        logger.warning(f"File blocked: {file_record.file_id} - {reason}")
        
        return ScanResult(
            passed=False,
            scan_status=ScanStatus.BLOCKED,
            risk_score=risk_score,
            details=details,
            block_reason=reason,
        )
    
    def _log_event(
        self,
        file_id: str,
        event_type: str,
        check_type: str | None = None,
        check_result: str | None = None,
        severity: str = "info",
        block_reason: str | None = None,
        risk_score: int | None = None,
        details: dict[str, Any] | None = None,
        is_blocked: bool = False,
    ) -> UploadSecurityEvent:
        file_record = self.file_service.get_file_by_id(file_id)
        
        event = UploadSecurityEvent(
            event_type=event_type,
            event_time=_utcnow(),
            file_id=file_id,
            file_name=file_record.original_name if file_record else None,
            file_size=file_record.file_size if file_record else None,
            file_hash=file_record.file_hash if file_record else None,
            upload_user_id=file_record.upload_user_id if file_record else None,
            severity=severity,
            check_type=check_type,
            check_result=check_result,
            check_details=json.dumps(details, ensure_ascii=False) if details else None,
            block_reason=block_reason,
            risk_score=risk_score,
            is_blocked=is_blocked,
        )
        
        self.db.add(event)
        self.db.commit()
        
        return event
    
    def quick_validate(
        self,
        filename: str,
        file_size: int,
        content_type: str | None = None,
    ) -> SecurityCheckResult:
        from app.models.file import AllowedFileTypes
        
        details = {
            "filename": filename,
            "file_size": file_size,
            "content_type": content_type,
        }
        
        extension = self._get_extension(filename)
        details["extension"] = extension
        
        if not AllowedFileTypes.is_allowed_extension(extension):
            return SecurityCheckResult(
                allowed=False,
                risk_score=100,
                reasons=[f"不允许的文件类型: {extension}"],
                details=details,
            )
        
        if file_size > settings.MAX_FILE_SIZE:
            max_mb = settings.MAX_FILE_SIZE // (1024 * 1024)
            return SecurityCheckResult(
                allowed=False,
                risk_score=100,
                reasons=[f"文件大小超过限制（最大 {max_mb}MB）"],
                details=details,
            )
        
        details["allowed_types"] = AllowedFileTypes.get_allowed_extensions()
        details["max_size_mb"] = settings.MAX_FILE_SIZE // (1024 * 1024)
        
        return SecurityCheckResult(
            allowed=True,
            risk_score=self._get_extension_risk(extension),
            reasons=[],
            details=details,
        )
    
    def _get_extension(self, filename: str) -> str:
        _, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        return f".{ext.lower()}" if ext else ""
    
    def get_security_events(
        self,
        user_id: int | None = None,
        file_id: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[UploadSecurityEvent], int]:
        query = self.db.query(UploadSecurityEvent)
        
        if user_id:
            query = query.filter(UploadSecurityEvent.upload_user_id == user_id)
        
        if file_id:
            query = query.filter(UploadSecurityEvent.file_id == file_id)
        
        if event_type:
            query = query.filter(UploadSecurityEvent.event_type == event_type)
        
        if severity:
            query = query.filter(UploadSecurityEvent.severity == severity)
        
        total = query.count()
        
        events = query.order_by(
            UploadSecurityEvent.event_time.desc()
        ).offset(offset).limit(limit).all()
        
        return events, total

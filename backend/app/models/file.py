"""
专利-标准比对系统 V1.0
M04 文件上传与安全网关模块 - 数据模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Index, Enum
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class FileType:
    PATENT = "patent"
    STANDARD = "standard"
    EXCEL_IMPORT = "excel_import"
    OTHER = "other"


class FileStatus:
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    BLOCKED = "blocked"


class ScanStatus:
    PENDING = "pending"
    SCANNING = "scanning"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class File(BaseModel):
    __tablename__ = "files"
    __table_args__ = {"comment": "文件元数据表"}

    file_id = Column(String(64), unique=True, nullable=False, index=True, comment="文件唯一标识 UUID")
    original_name = Column(String(256), nullable=False, comment="原始文件名")
    stored_name = Column(String(256), nullable=False, comment="存储文件名")
    file_path = Column(String(512), nullable=False, comment="文件存储路径")
    
    file_type = Column(String(32), nullable=False, index=True, comment="文件类型：patent/standard/excel_import/other")
    file_category = Column(String(32), nullable=True, comment="文件分类：pdf/word/excel/txt")
    
    file_size = Column(Integer, nullable=False, default=0, comment="文件大小(字节)")
    page_count = Column(Integer, nullable=True, comment="页数(PDF/Word)")
    file_hash = Column(String(128), nullable=True, index=True, comment="文件哈希值(SHA256)")
    
    mime_type = Column(String(128), nullable=True, comment="MIME类型")
    file_extension = Column(String(16), nullable=True, comment="文件扩展名")
    
    status = Column(String(32), nullable=False, default=FileStatus.PENDING, index=True, comment="文件状态")
    
    scan_status = Column(String(32), nullable=True, default=ScanStatus.PENDING, comment="安全扫描状态")
    scan_result = Column(Text, nullable=True, comment="扫描结果详情(JSON)")
    scan_time = Column(DateTime, nullable=True, comment="扫描完成时间")
    
    upload_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="上传用户ID")
    upload_ip = Column(String(64), nullable=True, comment="上传IP地址")
    upload_source = Column(String(64), nullable=True, comment="上传来源：web/api")
    
    task_id = Column(String(64), nullable=True, index=True, comment="关联任务ID")
    
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    is_deleted = Column(Boolean, default=False, nullable=False, index=True, comment="是否已删除")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")
    
    file_metadata = Column("metadata", Text, nullable=True, comment="扩展元数据(JSON)")
    tags = Column(Text, nullable=True, comment="标签列表(JSON数组)")
    
    upload_user = relationship("User", backref="uploaded_files")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.file_id:
            self.file_id = uuid.uuid4().hex
    
    def to_dict(self) -> dict:
        data = super().to_dict()
        data["file_id"] = self.file_id
        data["original_name"] = self.original_name
        data["stored_name"] = self.stored_name
        data["file_path"] = self.file_path
        data["file_type"] = self.file_type
        data["file_category"] = self.file_category
        data["file_size"] = self.file_size
        data["page_count"] = self.page_count
        data["file_hash"] = self.file_hash
        data["mime_type"] = self.mime_type
        data["file_extension"] = self.file_extension
        data["status"] = self.status
        data["scan_status"] = self.scan_status
        data["upload_user_id"] = self.upload_user_id
        data["upload_ip"] = self.upload_ip
        data["task_id"] = self.task_id
        data["is_active"] = self.is_active
        data["is_deleted"] = self.is_deleted
        return data
    
    def __repr__(self) -> str:
        return f"<File id={self.id} file_id={self.file_id} original_name={self.original_name}>"


class UploadSecurityEvent(BaseModel):
    __tablename__ = "upload_security_events"
    __table_args__ = (
        Index("ix_upload_security_events_event_time", "event_time"),
        {"comment": "上传安全事件表"},
    )
    
    event_id = Column(String(64), unique=True, nullable=False, index=True, comment="事件唯一标识")
    event_type = Column(String(64), nullable=False, index=True, comment="事件类型")
    event_time = Column(DateTime, nullable=False, default=datetime.utcnow, comment="事件时间")
    
    file_id = Column(String(64), nullable=True, index=True, comment="关联文件ID")
    file_name = Column(String(256), nullable=True, comment="文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小")
    file_hash = Column(String(128), nullable=True, comment="文件哈希")
    
    upload_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="上传用户ID")
    upload_ip = Column(String(64), nullable=True, comment="上传IP地址")
    user_agent = Column(String(512), nullable=True, comment="用户代理")
    
    severity = Column(String(32), nullable=False, default="info", comment="严重程度：info/warning/high/critical")
    
    check_type = Column(String(64), nullable=True, comment="检测类型：file_type/size/virus/content")
    check_result = Column(String(32), nullable=True, comment="检测结果：passed/failed/blocked")
    check_details = Column(Text, nullable=True, comment="检测详情(JSON)")
    
    block_reason = Column(String(256), nullable=True, comment="阻断原因")
    risk_score = Column(Integer, nullable=True, comment="风险评分 0-100")
    
    action_taken = Column(String(64), nullable=True, comment="采取的行动")
    is_blocked = Column(Boolean, default=False, nullable=False, comment="是否被阻断")
    
    event_metadata = Column("metadata", Text, nullable=True, comment="扩展元数据(JSON)")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.event_id:
            self.event_id = uuid.uuid4().hex
    
    def __repr__(self) -> str:
        return f"<UploadSecurityEvent id={self.id} event_type={self.event_type} severity={self.severity}>"


class SecurityEventType:
    FILE_UPLOAD_START = "file.upload.start"
    FILE_UPLOAD_COMPLETE = "file.upload.complete"
    FILE_TYPE_CHECK = "file.check.type"
    FILE_SIZE_CHECK = "file.check.size"
    FILE_PAGE_CHECK = "file.check.page"
    FILE_VIRUS_SCAN = "file.scan.virus"
    FILE_CONTENT_SCAN = "file.scan.content"
    FILE_HASH_DUPLICATE = "file.hash.duplicate"
    FILE_BLOCKED = "file.blocked"
    FILE_DELETED = "file.deleted"
    SECURITY_POLICY_VIOLATION = "security.policy.violation"


class AllowedFileTypes:
    PDF = ".pdf"
    DOC = ".doc"
    DOCX = ".docx"
    XLS = ".xls"
    XLSX = ".xlsx"
    TXT = ".txt"
    
    _allowed_extensions = [PDF, DOC, DOCX, XLS, XLSX, TXT]
    _allowed_mime_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
    ]
    
    @classmethod
    def get_allowed_extensions(cls) -> list[str]:
        return cls._allowed_extensions.copy()
    
    @classmethod
    def get_allowed_mime_types(cls) -> list[str]:
        return cls._allowed_mime_types.copy()
    
    @classmethod
    def is_allowed_extension(cls, extension: str) -> bool:
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        return ext in cls._allowed_extensions
    
    @classmethod
    def is_allowed_mime_type(cls, mime_type: str) -> bool:
        if not mime_type:
            return False
        mt = mime_type.lower().split(";")[0].strip()
        return mt in cls._allowed_mime_types
    
    @classmethod
    def get_file_category(cls, extension: str) -> str:
        ext = extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        
        if ext in [cls.PDF]:
            return "pdf"
        elif ext in [cls.DOC, cls.DOCX]:
            return "word"
        elif ext in [cls.XLS, cls.XLSX]:
            return "excel"
        elif ext in [cls.TXT]:
            return "txt"
        return "unknown"

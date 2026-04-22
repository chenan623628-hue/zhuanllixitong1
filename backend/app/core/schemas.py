"""
专利-标准比对系统 V1.0
M01 工程基线模块 - 统一数据模型
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=0, description="响应码，0 表示成功")
    message: str = Field(default="操作成功", description="响应消息")
    data: T | None = Field(default=None, description="响应数据")
    request_id: str = Field(default="", description="请求追踪 ID")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": 0,
                    "message": "操作成功",
                    "data": {"key": "value"},
                    "request_id": "trace-abc123"
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="健康状态")
    version: str = Field(description="服务版本")
    timestamp: str = Field(description="检查时间戳")


class ReadyResponse(BaseModel):
    status: str = Field(default="ready", description="就绪状态")
    version: str = Field(description="服务版本")
    checks: dict[str, bool] = Field(default_factory=dict, description="各组件检查结果")


class ErrorCode:
    SUCCESS = 0
    
    AUTH_INVALID_CREDENTIALS = 10001
    AUTH_TOKEN_EXPIRED = 10002
    AUTH_TOKEN_MISSING = 10003
    AUTH_PERMISSION_DENIED = 10004
    
    PERM_ACCESS_DENIED = 20001
    PERM_RESOURCE_NOT_FOUND = 20002
    PERM_ACTION_NOT_ALLOWED = 20003
    
    FILE_INVALID_TYPE = 30001
    FILE_TOO_LARGE = 30002
    FILE_TOO_MANY_PAGES = 30003
    FILE_UPLOAD_FAILED = 30004
    FILE_NOT_FOUND = 30005
    FILE_PARSE_ERROR = 30006
    
    TASK_NOT_FOUND = 40001
    TASK_STATUS_INVALID = 40002
    TASK_CREATE_FAILED = 40003
    TASK_CANCEL_FAILED = 40004
    
    ENGINE_INIT_FAILED = 50001
    ENGINE_COMPARE_FAILED = 50002
    ENGINE_TIMEOUT = 50003
    ENGINE_LLM_ERROR = 50004
    
    REPORT_GENERATE_FAILED = 60001
    REPORT_NOT_FOUND = 60002
    REPORT_EXPORT_FAILED = 60003
    
    AUDIT_LOG_FAILED = 70001
    
    VALIDATION_ERROR = 80001
    INTERNAL_ERROR = 90001
    SERVICE_UNAVAILABLE = 90002


class ErrorMessage:
    _messages = {
        ErrorCode.SUCCESS: "操作成功",
        
        ErrorCode.AUTH_INVALID_CREDENTIALS: "用户名或密码错误",
        ErrorCode.AUTH_TOKEN_EXPIRED: "登录已过期，请重新登录",
        ErrorCode.AUTH_TOKEN_MISSING: "未登录，请先登录",
        ErrorCode.AUTH_PERMISSION_DENIED: "权限不足",
        
        ErrorCode.PERM_ACCESS_DENIED: "无权访问该资源",
        ErrorCode.PERM_RESOURCE_NOT_FOUND: "资源不存在",
        ErrorCode.PERM_ACTION_NOT_ALLOWED: "不允许执行该操作",
        
        ErrorCode.FILE_INVALID_TYPE: "不支持的文件格式，仅支持 PDF/Word/TXT",
        ErrorCode.FILE_TOO_LARGE: "文件大小超过限制（10MB）",
        ErrorCode.FILE_TOO_MANY_PAGES: "文件页数超过限制（500页）",
        ErrorCode.FILE_UPLOAD_FAILED: "文件上传失败",
        ErrorCode.FILE_NOT_FOUND: "文件不存在",
        ErrorCode.FILE_PARSE_ERROR: "文件解析失败",
        
        ErrorCode.TASK_NOT_FOUND: "任务不存在",
        ErrorCode.TASK_STATUS_INVALID: "任务状态无效",
        ErrorCode.TASK_CREATE_FAILED: "任务创建失败",
        ErrorCode.TASK_CANCEL_FAILED: "任务取消失败",
        
        ErrorCode.ENGINE_INIT_FAILED: "比对引擎初始化失败",
        ErrorCode.ENGINE_COMPARE_FAILED: "比对执行失败",
        ErrorCode.ENGINE_TIMEOUT: "比对超时",
        ErrorCode.ENGINE_LLM_ERROR: "LLM 调用失败",
        
        ErrorCode.REPORT_GENERATE_FAILED: "报告生成失败",
        ErrorCode.REPORT_NOT_FOUND: "报告不存在",
        ErrorCode.REPORT_EXPORT_FAILED: "报告导出失败",
        
        ErrorCode.AUDIT_LOG_FAILED: "审计日志记录失败",
        
        ErrorCode.VALIDATION_ERROR: "参数校验失败",
        ErrorCode.INTERNAL_ERROR: "服务器内部错误",
        ErrorCode.SERVICE_UNAVAILABLE: "服务暂时不可用",
    }

    @classmethod
    def get(cls, code: int) -> str:
        return cls._messages.get(code, "未知错误")

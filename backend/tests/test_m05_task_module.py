"""
M05 任务管理模块全面测试脚本 - 使用 pytest assert 风格
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.task import (
    Task, TaskEvent, TaskType, TaskStatus, TaskStatusTransition,
    PriorityLevel, TaskEventType, TaskStep
)
from app.services.task.state_machine_service import StateMachineService, TransitionResult
from app.services.task.event_service import EventService
from app.services.task.task_service import (
    TaskService, CreateTaskContext, UpdateProgressContext,
    DEFAULT_LEASE_DURATION_SECONDS, HEARTBEAT_EXTEND_SECONDS,
)
from app.core.exceptions import TaskException


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    """创建内存数据库用于测试"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestStatusMachineLogic:
    """测试状态机逻辑"""
    
    def test_valid_transitions_pending(self):
        """测试 pending 状态的有效转移"""
        assert TaskStatusTransition.can_transition(TaskStatus.PENDING, TaskStatus.PARSING) is True
        assert TaskStatusTransition.can_transition(TaskStatus.PENDING, TaskStatus.CANCELLED) is True
        assert TaskStatusTransition.can_transition(TaskStatus.PENDING, TaskStatus.FAILED) is True
    
    def test_invalid_transitions_pending(self):
        """测试 pending 状态的无效转移"""
        assert TaskStatusTransition.can_transition(TaskStatus.PENDING, TaskStatus.ARCHIVED) is False
        assert TaskStatusTransition.can_transition(TaskStatus.PENDING, TaskStatus.REVIEWED) is False
    
    def test_valid_transitions_parsing(self):
        """测试 parsing 状态的有效转移"""
        assert TaskStatusTransition.can_transition(TaskStatus.PARSING, TaskStatus.COMPARING) is True
        assert TaskStatusTransition.can_transition(TaskStatus.PARSING, TaskStatus.CANCELLED) is True
        assert TaskStatusTransition.can_transition(TaskStatus.PARSING, TaskStatus.FAILED) is True
    
    def test_valid_transitions_comparing(self):
        """测试 comparing 状态的有效转移"""
        assert TaskStatusTransition.can_transition(TaskStatus.COMPARING, TaskStatus.REVIEW_PENDING) is True
        assert TaskStatusTransition.can_transition(TaskStatus.COMPARING, TaskStatus.CANCELLED) is True
        assert TaskStatusTransition.can_transition(TaskStatus.COMPARING, TaskStatus.FAILED) is True
    
    def test_valid_transitions_review(self):
        """测试 review 状态的有效转移"""
        assert TaskStatusTransition.can_transition(TaskStatus.REVIEW_PENDING, TaskStatus.REVIEWED) is True
        assert TaskStatusTransition.can_transition(TaskStatus.REVIEWED, TaskStatus.REPORT_READY) is True
        assert TaskStatusTransition.can_transition(TaskStatus.REPORT_READY, TaskStatus.ARCHIVED) is True
    
    def test_retryable_statuses(self):
        """测试可重试状态"""
        assert TaskStatusTransition.is_retryable(TaskStatus.FAILED) is True
        assert TaskStatusTransition.is_retryable(TaskStatus.CANCELLED) is True
        assert TaskStatusTransition.is_retryable(TaskStatus.PENDING) is False
        assert TaskStatusTransition.is_retryable(TaskStatus.ARCHIVED) is False
    
    def test_cancellable_statuses(self):
        """测试可取消状态"""
        assert TaskStatusTransition.is_cancellable(TaskStatus.PENDING) is True
        assert TaskStatusTransition.is_cancellable(TaskStatus.PARSING) is True
        assert TaskStatusTransition.is_cancellable(TaskStatus.COMPARING) is True
        assert TaskStatusTransition.is_cancellable(TaskStatus.ARCHIVED) is False
        assert TaskStatusTransition.is_cancellable(TaskStatus.FAILED) is False
    
    def test_final_statuses(self):
        """测试终止状态"""
        assert TaskStatusTransition.is_final(TaskStatus.ARCHIVED) is True
        assert TaskStatusTransition.is_final(TaskStatus.FAILED) is True
        assert TaskStatusTransition.is_final(TaskStatus.CANCELLED) is True
        assert TaskStatusTransition.is_final(TaskStatus.PENDING) is False
        assert TaskStatusTransition.is_final(TaskStatus.PARSING) is False
    
    def test_running_statuses(self):
        """测试运行中状态"""
        assert TaskStatusTransition.is_running(TaskStatus.PARSING) is True
        assert TaskStatusTransition.is_running(TaskStatus.COMPARING) is True
        assert TaskStatusTransition.is_running(TaskStatus.PENDING) is False
    
    def test_full_workflow_transitions(self):
        """测试完整工作流的所有状态转移"""
        workflow = [
            TaskStatus.PENDING,
            TaskStatus.PARSING,
            TaskStatus.COMPARING,
            TaskStatus.REVIEW_PENDING,
            TaskStatus.REVIEWED,
            TaskStatus.REPORT_READY,
            TaskStatus.ARCHIVED,
        ]
        
        for i in range(len(workflow) - 1):
            from_status = workflow[i]
            to_status = workflow[i + 1]
            assert TaskStatusTransition.can_transition(from_status, to_status) is True


class TestTaskModel:
    """测试任务模型"""
    
    def test_task_model_basic(self, db):
        """测试任务模型基础功能"""
        task = Task(
            task_name="测试任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
            status=TaskStatus.PENDING,
            priority=PriorityLevel.NORMAL,
            progress_percent=0,
            retry_count=0,
        )
        task.set_patent_file_ids(["pat_001"])
        task.set_metadata({"test_key": "test_value"})
        task.set_tags(["tag1", "tag2"])
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        assert task.task_id is not None
        assert task.status == TaskStatus.PENDING
        assert task.task_type == TaskType.ONE_TO_ONE
        assert task.get_patent_file_ids() == ["pat_001"]
        assert task.get_metadata() == {"test_key": "test_value"}
        assert task.get_tags() == ["tag1", "tag2"]
    
    def test_task_model_n_to_1(self, db):
        """测试 N:1 任务模型"""
        task = Task(
            task_name="N:1 测试任务",
            task_type=TaskType.N_TO_ONE,
            standard_file_id="std_456",
        )
        task.set_patent_file_ids(["pat_001", "pat_002", "pat_003"])
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        assert task.task_type == TaskType.N_TO_ONE
        assert task.patent_file_id is None
        assert task.get_patent_file_ids() == ["pat_001", "pat_002", "pat_003"]
    
    def test_task_to_dict(self, db):
        """测试任务 to_dict 方法"""
        task = Task(
            task_name="to_dict 测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_789",
            priority=PriorityLevel.HIGH,
        )
        task.set_patent_file_ids(["pat_100"])
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        task_dict = task.to_dict()
        
        assert task_dict["task_id"] == task.task_id
        assert task_dict["task_name"] == "to_dict 测试"
        assert task_dict["status"] == TaskStatus.PENDING
        assert task_dict["priority"] == PriorityLevel.HIGH
        assert task_dict["patent_file_ids"] == ["pat_100"]


class TestEventModel:
    """测试事件模型"""
    
    def test_event_model_basic(self, db):
        """测试事件模型基础功能"""
        task = Task(
            task_name="事件测试任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        event = TaskEvent(
            event_type=TaskEventType.TASK_CREATED,
            task_id=task.task_id,
            event_message="任务创建",
            progress_percent=0,
        )
        event.set_event_details({"detail": "test"})
        
        db.add(event)
        db.commit()
        db.refresh(event)
        
        assert event.event_id is not None
        assert event.event_type == TaskEventType.TASK_CREATED
        assert event.task_id == task.task_id
        assert event.get_event_details() == {"detail": "test"}


class TestFullWorkflow:
    """测试完整工作流"""
    
    def test_full_workflow_execution(self, db):
        """测试完整工作流执行"""
        task = Task(
            task_name="完整工作流测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
            priority=PriorityLevel.HIGH,
            progress_percent=0,
            retry_count=0,
            max_retries=3,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        worker_id = "worker_001"
        
        assert task.status == TaskStatus.PENDING
        
        result = sm.transition(
            task=task,
            to_status=TaskStatus.PARSING,
            event_message="开始解析文件",
            worker_id=worker_id,
            progress_percent=10,
            progress_message="正在解析...",
        )
        assert result.success is True
        assert task.status == TaskStatus.PARSING
        assert task.progress_percent == 10
        
        result = sm.transition(
            task=task,
            to_status=TaskStatus.COMPARING,
            event_message="解析完成，进入比对",
            worker_id=worker_id,
            progress_percent=30,
        )
        assert result.success is True
        assert task.status == TaskStatus.COMPARING
        
        result = sm.transition(
            task=task,
            to_status=TaskStatus.REVIEW_PENDING,
            event_message="比对完成，等待校验",
            worker_id=worker_id,
            progress_percent=70,
        )
        assert result.success is True
        assert task.status == TaskStatus.REVIEW_PENDING
        
        result = sm.transition(
            task=task,
            to_status=TaskStatus.REVIEWED,
            event_message="人工校验完成",
            user_id=1,
            progress_percent=85,
        )
        assert result.success is True
        assert task.status == TaskStatus.REVIEWED
        
        result = sm.transition(
            task=task,
            to_status=TaskStatus.REPORT_READY,
            event_message="报告已就绪",
            progress_percent=95,
        )
        assert result.success is True
        assert task.status == TaskStatus.REPORT_READY
        
        result = sm.transition(
            task=task,
            to_status=TaskStatus.ARCHIVED,
            event_message="任务完成",
            progress_percent=100,
        )
        assert result.success is True
        assert task.status == TaskStatus.ARCHIVED
        assert task.progress_percent == 100
        assert task.is_archived is True


class TestCancelAndRetry:
    """测试取消和重试功能"""
    
    def test_cancel_from_parsing(self, db):
        """测试从解析状态取消"""
        task = Task(
            task_name="取消测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PARSING,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        sm.cancel_task(task, reason="用户取消", user_id=1)
        
        assert task.status == TaskStatus.CANCELLED
        assert task.cancelled_at is not None
    
    def test_retry_after_failure(self, db):
        """测试失败后重试"""
        task = Task(
            task_name="重试测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.FAILED,
            retry_count=0,
            max_retries=3,
            error_code="TEST_ERROR",
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        sm.retry_task(task, user_id=1)
        
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1
        assert task.error_code is None
    
    def test_max_retries_limit(self, db):
        """测试最大重试次数限制"""
        task = Task(
            task_name="最大重试测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        
        with pytest.raises(TaskException):
            sm.retry_task(task)


class TestInvalidTransitions:
    """测试无效状态转移"""
    
    def test_invalid_transition_raises_exception(self, db):
        """测试无效状态转移抛出异常"""
        task = Task(
            task_name="无效转移测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        
        with pytest.raises(TaskException):
            sm.transition(task, TaskStatus.ARCHIVED, "无效转移")
    
    def test_cancel_archived_raises_exception(self, db):
        """测试取消已归档任务抛出异常"""
        task = Task(
            task_name="已归档任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.ARCHIVED,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        
        with pytest.raises(TaskException):
            sm.cancel_task(task)


class TestLeaseMechanism:
    """测试租约机制"""
    
    def test_claim_task_atomic_update(self, db):
        """测试任务领取的原子更新（防止并发冲突）"""
        task = Task(
            task_name="租约测试任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        ts = TaskService(db)
        
        claimed = ts.claim_task("worker_001")
        
        assert claimed is not None
        assert claimed.worker_id == "worker_001"
        assert claimed.lease_acquired_at is not None
        assert claimed.lease_expires_at is not None
    
    def test_heartbeat_extends_lease(self, db):
        """测试心跳续租"""
        task = Task(
            task_name="心跳测试任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        ts = TaskService(db)
        
        claimed = ts.claim_task("worker_001")
        assert claimed is not None
        original_expires = claimed.lease_expires_at
        
        result = ts.heartbeat(claimed.task_id, "worker_001", extend_seconds=300)
        
        assert result is True
        
        db.refresh(claimed)
        assert claimed.lease_updated_at is not None
    
    def test_lease_expiration_reclamation(self, db):
        """测试租约过期回收"""
        task = Task(
            task_name="过期租约测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
        )
        task.set_patent_file_ids(["pat_001"])
        
        now = _utcnow()
        task.worker_id = "dead_worker"
        task.lease_acquired_at = now - timedelta(hours=1)
        task.lease_expires_at = now - timedelta(minutes=10)
        task.lease_updated_at = now - timedelta(hours=1)
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        ts = TaskService(db)
        
        reclaimed = ts.reclaim_expired_leases()
        
        assert reclaimed == 1
        
        db.refresh(task)
        assert task.worker_id is None
        assert task.lease_acquired_at is None
        assert task.lease_expires_at is None
    
    def test_task_complete_clears_lease(self, db):
        """测试任务完成后清除租约"""
        task = Task(
            task_name="完成清除租约测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.REPORT_READY,
            worker_id="worker_001",
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        ts = TaskService(db)
        ts.complete_task(task.task_id, "worker_001")
        
        db.refresh(task)
        assert task.worker_id is None
        assert task.lease_acquired_at is None
        assert task.lease_expires_at is None
        assert task.status == TaskStatus.ARCHIVED


class TestCreateTaskValidation:
    """测试创建任务时的验证"""
    
    def test_validate_empty_name(self, db):
        """测试空任务名"""
        ts = TaskService(db)
        
        ctx = CreateTaskContext(
            task_name="",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
            patent_file_ids=["pat_123"],
        )
        
        with pytest.raises(TaskException):
            ts.validate_create_context(ctx)
    
    def test_validate_empty_files(self, db):
        """测试空文件列表"""
        ts = TaskService(db)
        
        ctx = CreateTaskContext(
            task_name="有效名称",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
            patent_file_ids=[],
        )
        
        with pytest.raises(TaskException):
            ts.validate_create_context(ctx)
    
    def test_validate_one_to_one_multiple_patents(self, db):
        """测试 1:1 任务使用多个专利"""
        ts = TaskService(db)
        
        ctx = CreateTaskContext(
            task_name="有效名称",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
            patent_file_ids=["pat_1", "pat_2"],
        )
        
        with pytest.raises(TaskException):
            ts.validate_create_context(ctx)
    
    def test_validate_invalid_priority(self, db):
        """测试无效优先级"""
        ts = TaskService(db)
        
        ctx = CreateTaskContext(
            task_name="有效名称",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
            patent_file_ids=["pat_1"],
            priority=100,
        )
        
        with pytest.raises(TaskException):
            ts.validate_create_context(ctx)
        
        ctx_low = CreateTaskContext(
            task_name="有效名称",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
            patent_file_ids=["pat_1"],
            priority=0,
        )
        
        with pytest.raises(TaskException):
            ts.validate_create_context(ctx_low)


class TestGetTaskStatusHistory:
    """测试 get_task_status_history 的 limit 参数"""
    
    def test_limit_parameter_applied(self, db):
        """测试 limit 参数是否被正确应用"""
        task = Task(
            task_name="历史测试任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        es = EventService(db)
        
        for i in range(10):
            from_s = TaskStatus.PENDING
            to_s = TaskStatus.PARSING if i % 2 == 0 else TaskStatus.PENDING
            
            event = TaskEvent(
                event_type=TaskEventType.STATUS_CHANGE,
                task_id=task.task_id,
                from_status=from_s,
                to_status=to_s,
                event_message=f"状态变更 {i}",
            )
            db.add(event)
        db.commit()
        
        history = es.get_task_status_history(task_id=task.task_id, limit=5)
        
        assert len(history) == 5


class TestGetTaskStatistics:
    """测试任务统计"""
    
    def test_statistics_calculation(self, db):
        """测试统计计算"""
        statuses = [
            TaskStatus.PENDING, TaskStatus.PENDING,
            TaskStatus.PARSING,
            TaskStatus.COMPARING,
            TaskStatus.FAILED, TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.ARCHIVED,
        ]
        
        for i, status in enumerate(statuses):
            task = Task(
                task_name=f"统计任务 {i}",
                task_type=TaskType.ONE_TO_ONE,
                standard_file_id=f"std_{i}",
                status=status,
            )
            task.set_patent_file_ids([f"pat_{i}"])
            db.add(task)
        db.commit()
        
        ts = TaskService(db)
        stats = ts.get_task_statistics()
        
        assert stats["total"] == 8
        assert stats["by_status"][TaskStatus.PENDING] == 2
        assert stats["by_status"][TaskStatus.FAILED] == 2
        assert stats["summary"]["running"] == 2
        assert stats["summary"]["final"] == 4


class TestEventService:
    """测试事件服务"""
    
    def test_get_task_events_pagination(self, db):
        """测试事件分页"""
        task = Task(
            task_name="事件分页测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        es = EventService(db)
        
        for i in range(30):
            es.record_step_progress(
                task_id=task.task_id,
                step_name=f"step_{i}",
                progress_percent=i * 3,
                progress_message=f"步骤 {i}",
            )
        
        events, total = es.get_task_events(task_id=task.task_id, limit=10, offset=10)
        
        assert total == 30
        assert len(events) == 10


class TestStateMachineStatusSummary:
    """测试状态机状态摘要"""
    
    def test_status_summary(self, db):
        """测试状态摘要生成"""
        task = Task(
            task_name="状态摘要测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PARSING,
            progress_percent=25,
            progress_message="正在解析...",
            retry_count=1,
            max_retries=3,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        summary = sm.get_task_status_summary(task)
        
        assert summary["task_id"] == task.task_id
        assert summary["status"] == TaskStatus.PARSING
        assert summary["progress_percent"] == 25
        assert summary["is_final"] == False
        assert summary["is_running"] == True
        assert summary["is_cancellable"] == True
        assert summary["retry_count"] == 1
        assert TaskStatus.COMPARING in summary["valid_next_statuses"]


class TestTaskServiceGetLeaseStatus:
    """测试租约状态查询"""
    
    def test_get_lease_status(self, db):
        """测试获取租约状态"""
        task = Task(
            task_name="租约状态测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        ts = TaskService(db)
        
        no_lease = ts.get_lease_status(task.task_id)
        assert no_lease is not None
        assert no_lease["worker_id"] is None
        
        claimed = ts.claim_task("worker_001")
        assert claimed is not None
        
        lease_status = ts.get_lease_status(task.task_id)
        assert lease_status is not None
        assert lease_status["worker_id"] == "worker_001"
        assert lease_status["is_expired"] == False
        assert lease_status["seconds_remaining"] is not None
        assert lease_status["seconds_remaining"] > 0
    
    def test_get_lease_status_for_nonexistent_task(self, db):
        """测试不存在任务的租约状态"""
        ts = TaskService(db)
        
        result = ts.get_lease_status("nonexistent_task_id")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

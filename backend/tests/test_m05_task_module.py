"""
M05 任务管理模块全面测试脚本

使用内存数据库进行端到端测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.task import (
    Task, TaskEvent, TaskType, TaskStatus, TaskStatusTransition,
    PriorityLevel, TaskEventType, TaskStep, StateMachine
)
from app.services.task.state_machine_service import StateMachineService, TransitionResult
from app.services.task.event_service import EventService
from app.services.task.task_service import (
    TaskService, CreateTaskContext, UpdateProgressContext
)
from app.core.exceptions import TaskException


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_test_db():
    """创建内存数据库"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine


def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_status_machine_logic():
    """测试状态机逻辑"""
    print_header("测试状态机逻辑")
    
    passed = 0
    failed = 0
    
    test_cases = [
        (TaskStatus.PENDING, TaskStatus.PARSING, True, "pending -> parsing"),
        (TaskStatus.PENDING, TaskStatus.CANCELLED, True, "pending -> cancelled"),
        (TaskStatus.PENDING, TaskStatus.FAILED, True, "pending -> failed"),
        (TaskStatus.PENDING, TaskStatus.ARCHIVED, False, "pending -> archived (INVALID)"),
        
        (TaskStatus.PARSING, TaskStatus.COMPARING, True, "parsing -> comparing"),
        (TaskStatus.PARSING, TaskStatus.CANCELLED, True, "parsing -> cancelled"),
        (TaskStatus.PARSING, TaskStatus.FAILED, True, "parsing -> failed"),
        (TaskStatus.PARSING, TaskStatus.PENDING, False, "parsing -> pending (INVALID)"),
        
        (TaskStatus.COMPARING, TaskStatus.REVIEW_PENDING, True, "comparing -> review_pending"),
        (TaskStatus.COMPARING, TaskStatus.CANCELLED, True, "comparing -> cancelled"),
        (TaskStatus.COMPARING, TaskStatus.FAILED, True, "comparing -> failed"),
        
        (TaskStatus.REVIEW_PENDING, TaskStatus.REVIEWED, True, "review_pending -> reviewed"),
        (TaskStatus.REVIEW_PENDING, TaskStatus.CANCELLED, True, "review_pending -> cancelled"),
        (TaskStatus.REVIEW_PENDING, TaskStatus.FAILED, True, "review_pending -> failed"),
        
        (TaskStatus.REVIEWED, TaskStatus.REPORT_READY, True, "reviewed -> report_ready"),
        (TaskStatus.REVIEWED, TaskStatus.FAILED, True, "reviewed -> failed"),
        (TaskStatus.REVIEWED, TaskStatus.PARSING, False, "reviewed -> parsing (INVALID)"),
        
        (TaskStatus.REPORT_READY, TaskStatus.ARCHIVED, True, "report_ready -> archived"),
        (TaskStatus.REPORT_READY, TaskStatus.PENDING, False, "report_ready -> pending (INVALID)"),
        
        (TaskStatus.FAILED, TaskStatus.PENDING, True, "failed -> pending (retry)"),
        (TaskStatus.CANCELLED, TaskStatus.PENDING, True, "cancelled -> pending (retry)"),
        (TaskStatus.ARCHIVED, TaskStatus.PENDING, False, "archived -> pending (INVALID)"),
    ]
    
    for from_s, to_s, expected, desc in test_cases:
        result = TaskStatusTransition.can_transition(from_s, to_s)
        if result == expected:
            print(f"  [PASS] {desc}")
            passed += 1
        else:
            print(f"  [FAIL] {desc} - expected={expected}, got={result}")
            failed += 1
    
    print(f"\n状态机测试: {passed} 通过, {failed} 失败")
    return failed == 0


def test_task_model_basic():
    """测试任务模型基础功能"""
    print_header("测试任务模型基础功能")
    
    db, engine = create_test_db()
    
    try:
        task = Task(
            task_name="测试任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
            status=TaskStatus.PENDING,
            priority=PriorityLevel.NORMAL,
            progress_percent=0,
            retry_count=0,
            max_retries=3,
        )
        
        task.set_patent_file_ids(["pat_001"])
        task.set_metadata({"test_key": "test_value"})
        task.set_tags(["tag1", "tag2"])
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        assert task.task_id is not None, "task_id 应该自动生成"
        assert task.status == TaskStatus.PENDING
        assert task.task_type == TaskType.ONE_TO_ONE
        assert task.get_patent_file_ids() == ["pat_001"]
        assert task.get_metadata() == {"test_key": "test_value"}
        assert task.get_tags() == ["tag1", "tag2"]
        
        print("  [PASS] 任务模型基础功能")
        
        patent_list = ["pat_001", "pat_002", "pat_003"]
        task2 = Task(
            task_name="N:1 测试任务",
            task_type=TaskType.N_TO_ONE,
            standard_file_id="std_456",
        )
        task2.set_patent_file_ids(patent_list)
        
        db.add(task2)
        db.commit()
        db.refresh(task2)
        
        assert task2.task_type == TaskType.N_TO_ONE
        assert task2.patent_file_id is None
        assert task2.get_patent_file_ids() == patent_list
        
        print("  [PASS] N:1 任务专利文件处理")
        
        task_dict = task.to_dict()
        assert task_dict["task_id"] == task.task_id
        assert task_dict["task_name"] == "测试任务"
        assert task_dict["status"] == TaskStatus.PENDING
        
        print("  [PASS] 任务 to_dict() 方法")
        
        print("\n任务模型测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_event_model():
    """测试事件模型"""
    print_header("测试事件模型")
    
    db, engine = create_test_db()
    
    try:
        task = Task(
            task_name="测试任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_123",
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
        
        event_dict = event.to_dict()
        assert event_dict["event_id"] == event.event_id
        assert event_dict["task_id"] == task.task_id
        
        print("  [PASS] 事件模型基础功能")
        print("\n事件模型测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_full_workflow():
    """测试完整工作流"""
    print_header("测试完整工作流 (StateMachineService)")
    
    db, engine = create_test_db()
    
    try:
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
        
        steps = [
            (TaskStatus.PARSING, 10, "开始解析文件", "worker_001"),
            (TaskStatus.COMPARING, 30, "解析完成，进入比对", "worker_001"),
            (TaskStatus.REVIEW_PENDING, 70, "比对完成，等待人工校验", "worker_001"),
            (TaskStatus.REVIEWED, 85, "人工校验完成", None),
            (TaskStatus.REPORT_READY, 95, "报告已就绪", None),
            (TaskStatus.ARCHIVED, 100, "任务完成", None),
        ]
        
        for to_status, progress, msg, worker in steps:
            from_status = task.status
            can = sm.can_transition(task, to_status)
            if not can:
                print(f"  [FAIL] {from_status} -> {to_status} 不允许")
                return False
            
            result = sm.transition(
                task=task,
                to_status=to_status,
                event_message=msg,
                worker_id=worker,
                progress_percent=progress,
                progress_message=msg,
            )
            
            assert result.success, f"转移失败: {from_status} -> {to_status}"
            assert task.status == to_status, f"状态未更新: 期望 {to_status}, 实际 {task.status}"
            assert task.progress_percent == progress, f"进度未更新: 期望 {progress}, 实际 {task.progress_percent}"
            
            print(f"  [PASS] {from_status} -> {to_status}")
        
        assert task.completed_at is not None
        assert task.is_archived == True
        assert task.progress_percent == 100
        
        print("\n  [PASS] 完整工作流执行成功")
        print("\n完整工作流测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_cancel_and_retry():
    """测试取消和重试功能"""
    print_header("测试取消和重试功能")
    
    db, engine = create_test_db()
    
    try:
        task = Task(
            task_name="取消重试测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
            progress_percent=0,
            retry_count=0,
            max_retries=3,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sm = StateMachineService(db)
        
        print("  测试 1: pending -> parsing -> cancelled")
        sm.transition(task, TaskStatus.PARSING, "开始执行", worker_id="worker_001", progress_percent=10)
        assert task.status == TaskStatus.PARSING
        print(f"    [PASS] pending -> parsing")
        
        sm.cancel_task(task, reason="用户取消", user_id=1)
        assert task.status == TaskStatus.CANCELLED
        assert task.cancelled_at is not None
        print(f"    [PASS] parsing -> cancelled")
        
        print("\n  测试 2: cancelled -> pending (重试)")
        sm.retry_task(task, user_id=1)
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1
        print(f"    [PASS] cancelled -> pending (retry_count=1)")
        
        print("\n  测试 3: pending -> parsing -> comparing -> failed")
        sm.transition(task, TaskStatus.PARSING, "开始执行", progress_percent=10)
        sm.transition(task, TaskStatus.COMPARING, "进入比对", progress_percent=30)
        print(f"    [PASS] pending -> parsing -> comparing")
        
        sm.mark_as_failed(task, "COMPARE_ERROR", "比对超时", worker_id="worker_001")
        assert task.status == TaskStatus.FAILED
        assert task.failed_at is not None
        assert task.error_code == "COMPARE_ERROR"
        print(f"    [PASS] comparing -> failed")
        
        print("\n  测试 4: 超过最大重试次数")
        task.retry_count = 3
        db.commit()
        db.refresh(task)
        
        try:
            sm.retry_task(task)
            print("    [FAIL] 应该抛出异常")
            return False
        except TaskException as e:
            print(f"    [PASS] 正确抛出异常: {e.message}")
        
        print("\n取消和重试测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_invalid_transitions():
    """测试无效状态转移"""
    print_header("测试无效状态转移")
    
    db, engine = create_test_db()
    
    try:
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
        
        invalid_transitions = [
            (TaskStatus.ARCHIVED, "pending -> archived"),
            (TaskStatus.REVIEWED, "pending -> reviewed"),
        ]
        
        for invalid_status, desc in invalid_transitions:
            try:
                sm.transition(task, invalid_status, "无效转移")
                print(f"  [FAIL] {desc} 应该失败但没有")
                return False
            except TaskException:
                print(f"  [PASS] {desc} 正确拒绝")
        
        task.status = TaskStatus.ARCHIVED
        db.commit()
        db.refresh(task)
        
        assert not TaskStatusTransition.is_cancellable(task.status)
        try:
            sm.cancel_task(task)
            print("  [FAIL] archived 任务不应该能取消")
            return False
        except TaskException:
            print("  [PASS] archived 任务无法取消")
        
        task.status = TaskStatus.ARCHIVED
        db.commit()
        assert not TaskStatusTransition.is_retryable(task.status)
        
        print("\n无效状态转移测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_event_service():
    """测试事件服务"""
    print_header("测试事件服务")
    
    db, engine = create_test_db()
    
    try:
        task = Task(
            task_name="事件服务测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
        )
        task.set_patent_file_ids(["pat_001"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        es = EventService(db)
        
        es.record_task_created(
            task_id=task.task_id,
            user_id=1,
            task_type=TaskType.ONE_TO_ONE,
            details={"test": "data"}
        )
        print("  [PASS] record_task_created")
        
        es.record_task_queued(task_id=task.task_id, queue_position=1)
        print("  [PASS] record_task_queued")
        
        es.record_task_started(task_id=task.task_id, worker_id="worker_001")
        print("  [PASS] record_task_started")
        
        es.record_step_progress(
            task_id=task.task_id,
            step_name="PDF解析",
            progress_percent=15,
            progress_message="正在解析专利PDF...",
            step_duration=5,
        )
        print("  [PASS] record_step_progress")
        
        es.record_task_completed(
            task_id=task.task_id,
            worker_id="worker_001",
            duration_seconds=120,
            details={"claims_analyzed": 25}
        )
        print("  [PASS] record_task_completed")
        
        events, total = es.get_task_events(task_id=task.task_id)
        print(f"  [PASS] get_task_events: {total} 条事件")
        
        status_history = es.get_task_status_history(task_id=task.task_id)
        print(f"  [PASS] get_task_status_history")
        
        latest = es.get_latest_event(task_id=task.task_id)
        assert latest is not None
        print(f"  [PASS] get_latest_event: {latest.event_type}")
        
        task2 = Task(
            task_name="错误事件测试",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_002",
        )
        task2.set_patent_file_ids(["pat_002"])
        db.add(task2)
        db.commit()
        db.refresh(task2)
        
        es.record_error(
            task_id=task2.task_id,
            error_code="PARSE_ERROR",
            error_message="PDF损坏无法解析",
            details={"page": 5}
        )
        print("  [PASS] record_error")
        
        es.record_task_failed(
            task_id=task2.task_id,
            error_code="PARSE_ERROR",
            error_message="PDF解析失败",
            worker_id="worker_001",
            from_status=TaskStatus.PARSING
        )
        print("  [PASS] record_task_failed")
        
        errors = es.get_task_error_events(task_id=task2.task_id)
        print(f"  [PASS] get_task_error_events: {len(errors)} 条错误")
        
        print("\n事件服务测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_task_service_api():
    """测试 TaskService 核心 API"""
    print_header("测试 TaskService 核心 API")
    
    db, engine = create_test_db()
    
    try:
        ts = TaskService(db)
        es = EventService(db)
        
        print("\n  测试 create_task 验证...")
        
        try:
            bad_ctx = CreateTaskContext(
                task_name="",
                task_type=TaskType.ONE_TO_ONE,
                standard_file_id="std_123",
                patent_file_ids=["pat_123"],
            )
            ts.validate_create_context(bad_ctx)
            print("    [FAIL] 空任务名应该被拒绝")
            return False
        except TaskException:
            print("    [PASS] 空任务名被正确拒绝")
        
        try:
            bad_ctx = CreateTaskContext(
                task_name="测试任务",
                task_type=TaskType.ONE_TO_ONE,
                standard_file_id="",
                patent_file_ids=["pat_123"],
            )
            ts.validate_create_context(bad_ctx)
            print("    [FAIL] 空标准文件应该被拒绝")
            return False
        except TaskException:
            print("    [PASS] 空标准文件被正确拒绝")
        
        try:
            bad_ctx = CreateTaskContext(
                task_name="测试任务",
                task_type=TaskType.ONE_TO_ONE,
                standard_file_id="std_123",
                patent_file_ids=[],
            )
            ts.validate_create_context(bad_ctx)
            print("    [FAIL] 空专利文件列表应该被拒绝")
            return False
        except TaskException:
            print("    [PASS] 空专利文件列表被正确拒绝")
        
        try:
            bad_ctx = CreateTaskContext(
                task_name="测试任务",
                task_type=TaskType.ONE_TO_ONE,
                standard_file_id="std_123",
                patent_file_ids=["p1", "p2"],
            )
            ts.validate_create_context(bad_ctx)
            print("    [FAIL] 1:1 任务只能有1个专利文件")
            return False
        except TaskException:
            print("    [PASS] 1:1 任务专利数量限制")
        
        print("\n  测试状态摘要...")
        task = Task(
            task_name="状态摘要测试",
            task_type=TaskType.N_TO_ONE,
            standard_file_id="std_001",
            status=TaskStatus.PENDING,
            priority=PriorityLevel.NORMAL,
        )
        task.set_patent_file_ids(["p1", "p2", "p3"])
        db.add(task)
        db.commit()
        db.refresh(task)
        
        sms = StateMachineService(db)
        summary = sms.get_task_status_summary(task)
        
        assert summary["task_id"] == task.task_id
        assert summary["status"] == TaskStatus.PENDING
        assert summary["is_final"] == False
        assert summary["is_cancellable"] == True
        assert summary["is_retryable"] == False
        
        print("    [PASS] get_task_status_summary")
        
        print("\n  测试统计方法...")
        for i in range(5):
            t = Task(
                task_name=f"统计测试任务 {i}",
                task_type=TaskType.ONE_TO_ONE,
                standard_file_id=f"std_{i}",
                status=TaskStatus.PENDING,
            )
            t.set_patent_file_ids([f"pat_{i}"])
            db.add(t)
        
        t_failed = Task(
            task_name="失败任务",
            task_type=TaskType.ONE_TO_ONE,
            standard_file_id="std_failed",
            status=TaskStatus.FAILED,
        )
        t_failed.set_patent_file_ids(["pat_failed"])
        db.add(t_failed)
        db.commit()
        
        stats = ts.get_task_statistics()
        
        assert stats["total"] == 7
        assert stats["by_status"][TaskStatus.PENDING] == 6
        assert stats["by_status"][TaskStatus.FAILED] == 1
        assert stats["summary"]["final"] == 1
        
        print("    [PASS] get_task_statistics")
        
        print("\n  测试任务列表查询...")
        tasks, total = ts.get_user_tasks(
            user_id=None,
            is_admin=True,
            status=TaskStatus.PENDING,
            limit=10,
        )
        
        assert total == 6
        assert len(tasks) == 6
        
        print("    [PASS] get_user_tasks")
        
        print("\n  测试批量搜索...")
        tasks, total = ts.get_user_tasks(
            user_id=None,
            is_admin=True,
            search="统计测试",
        )
        assert total == 5
        print("    [PASS] 任务搜索功能")
        
        print("\nTaskService 核心 API 测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_status_config_and_helpers():
    """测试状态配置和辅助函数"""
    print_header("测试状态配置和辅助函数")
    
    try:
        from app.models.task import TaskStatus, TaskStatusTransition
        
        print("\n  测试状态分组...")
        assert TaskStatus.PENDING in TaskStatusTransition.QUEUE_STATUSES
        assert TaskStatus.PARSING in TaskStatusTransition.RUNNING_STATUSES
        assert TaskStatus.COMPARING in TaskStatusTransition.RUNNING_STATUSES
        assert TaskStatus.REVIEW_PENDING in TaskStatusTransition.WAITING_STATUSES
        assert TaskStatus.REPORT_READY in TaskStatusTransition.WAITING_STATUSES
        assert TaskStatus.ARCHIVED in TaskStatusTransition.FINAL_STATUSES
        assert TaskStatus.FAILED in TaskStatusTransition.FINAL_STATUSES
        assert TaskStatus.CANCELLED in TaskStatusTransition.FINAL_STATUSES
        print("    [PASS] 状态分组正确")
        
        print("\n  测试 is_cancellable...")
        assert TaskStatusTransition.is_cancellable(TaskStatus.PENDING)
        assert TaskStatusTransition.is_cancellable(TaskStatus.PARSING)
        assert TaskStatusTransition.is_cancellable(TaskStatus.COMPARING)
        assert not TaskStatusTransition.is_cancellable(TaskStatus.ARCHIVED)
        assert not TaskStatusTransition.is_cancellable(TaskStatus.FAILED)
        print("    [PASS] is_cancellable 正确")
        
        print("\n  测试 is_retryable...")
        assert TaskStatusTransition.is_retryable(TaskStatus.FAILED)
        assert TaskStatusTransition.is_retryable(TaskStatus.CANCELLED)
        assert not TaskStatusTransition.is_retryable(TaskStatus.PENDING)
        assert not TaskStatusTransition.is_retryable(TaskStatus.ARCHIVED)
        print("    [PASS] is_retryable 正确")
        
        print("\n  测试 is_final...")
        assert TaskStatusTransition.is_final(TaskStatus.ARCHIVED)
        assert TaskStatusTransition.is_final(TaskStatus.FAILED)
        assert TaskStatusTransition.is_final(TaskStatus.CANCELLED)
        assert not TaskStatusTransition.is_final(TaskStatus.PENDING)
        assert not TaskStatusTransition.is_final(TaskStatus.PARSING)
        print("    [PASS] is_final 正确")
        
        print("\n  测试 is_running...")
        assert TaskStatusTransition.is_running(TaskStatus.PARSING)
        assert TaskStatusTransition.is_running(TaskStatus.COMPARING)
        assert not TaskStatusTransition.is_running(TaskStatus.PENDING)
        assert not TaskStatusTransition.is_running(TaskStatus.ARCHIVED)
        print("    [PASS] is_running 正确")
        
        print("\n状态配置和辅助函数测试: 全部通过")
        return True
        
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#"*70)
    print("#" + " " * 68 + "#")
    print("#   M05 任务管理模块 - 全面深度测试".ljust(67) + "#")
    print("#" + " " * 68 + "#")
    print("#"*70)
    
    results = []
    
    tests = [
        ("状态机逻辑测试", test_status_machine_logic),
        ("任务模型基础测试", test_task_model_basic),
        ("事件模型测试", test_event_model),
        ("完整工作流测试", test_full_workflow),
        ("取消重试测试", test_cancel_and_retry),
        ("无效转移测试", test_invalid_transitions),
        ("事件服务测试", test_event_service),
        ("TaskService API 测试", test_task_service_api),
        ("状态配置测试", test_status_config_and_helpers),
    ]
    
    for name, test_fn in tests:
        result = test_fn()
        results.append((name, result))
    
    print("\n" + "="*70)
    print("  测试结果汇总")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        if result:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}")
            failed += 1
    
    print("\n" + "-"*70)
    print(f"  总计: {passed} 通过, {failed} 失败")
    print("-"*70)
    
    if failed == 0:
        print("\n" + "="*70)
        print("  ✅ 所有测试通过! M05 模块可以安全使用")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("  ❌ 部分测试失败，请检查修复")
        print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

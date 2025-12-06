"""
调度器测试

测试 Scheduler 的基本功能
"""

import pytest
try:
    import cloudpickle as pickle
except ImportError:
    import pickle
import miniray._miniray_core as core


def double(x):
    """测试函数：返回 x * 2"""
    return x * 2


class TestScheduler:
    """Scheduler 测试类"""

    def test_create_scheduler(self, temp_scheduler):
        """测试创建 Scheduler"""
        scheduler = temp_scheduler
        assert scheduler.get_pending_task_count() == 0, "新创建的 Scheduler 应该没有任务"

    def test_submit_and_get_task(self, temp_scheduler):
        """测试提交和获取任务"""
        scheduler = temp_scheduler

        # 创建任务
        task = core.Task()
        task.return_ref = core.ObjectRef()
        task.serialized_function = list(pickle.dumps(double))
        task.serialized_args = list(pickle.dumps((21,)))

        # 提交任务
        scheduler.submit_task(task)
        assert scheduler.get_pending_task_count() == 1, "应该有 1 个待处理任务"

        # 获取任务
        retrieved_task = scheduler.get_next_task()
        assert retrieved_task is not None, "应该能获取到任务"
        assert retrieved_task.return_ref == task.return_ref, "任务的 return_ref 应该一致"

        # 队列应该为空
        assert scheduler.get_pending_task_count() == 0, "获取任务后队列应该为空"

    def test_empty_queue(self, temp_scheduler):
        """测试空队列"""
        scheduler = temp_scheduler
        task = scheduler.get_next_task()
        assert task is None, "空队列应该返回 None"

    def test_multiple_tasks(self, temp_scheduler):
        """测试多个任务"""
        scheduler = temp_scheduler

        # 提交多个任务
        tasks = []
        for i in range(5):
            task = core.Task()
            task.return_ref = core.ObjectRef()
            task.serialized_function = list(pickle.dumps(double))
            task.serialized_args = list(pickle.dumps((i,)))
            scheduler.submit_task(task)
            tasks.append(task)

        assert scheduler.get_pending_task_count() == 5, "应该有 5 个待处理任务"

        # 获取所有任务
        for i in range(5):
            retrieved_task = scheduler.get_next_task()
            assert retrieved_task is not None, f"应该能获取到第 {i} 个任务"

        assert scheduler.get_pending_task_count() == 0, "所有任务获取后队列应该为空"

    def test_worker_registration(self, temp_scheduler):
        """测试 Worker 注册"""
        scheduler = temp_scheduler

        # 注册 Worker
        scheduler.register_worker(1)
        assert scheduler.get_idle_worker_count() == 1, "应该有 1 个空闲 Worker"

        # 标记 Worker 为忙碌
        scheduler.mark_worker_busy(1)
        assert scheduler.get_idle_worker_count() == 0, "不应该有空闲 Worker"

        # 标记 Worker 为空闲
        scheduler.mark_worker_idle(1)
        assert scheduler.get_idle_worker_count() == 1, "应该有 1 个空闲 Worker"

        # 注销 Worker
        scheduler.unregister_worker(1)
        assert scheduler.get_idle_worker_count() == 0, "注销后不应该有空闲 Worker"

    def test_has_idle_worker(self, temp_scheduler):
        """测试检查是否有空闲 Worker"""
        scheduler = temp_scheduler

        assert not scheduler.has_idle_worker(), "应该没有空闲 Worker"

        scheduler.register_worker(1)
        assert scheduler.has_idle_worker(), "应该有空闲 Worker"

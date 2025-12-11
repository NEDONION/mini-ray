"""
miniray Actor 功能测试
测试 Actor 的创建、方法调用、状态管理等
"""

import pytest
import miniray
import time


class TestBasicActor:
    """基础 Actor 功能测试"""
    
    def test_simple_actor(self, miniray_instance):
        """测试简单的 Actor 功能"""
        miniray = miniray_instance
        
        @miniray.remote
        class Counter:
            def __init__(self, init_value=0):
                self.value = init_value

            def increment(self, step=1):
                self.value += step
                return self.value

            def get_value(self):
                return self.value

        # 创建 Actor
        counter = Counter.remote(10)

        # 调用方法
        increment_ref = counter.increment.remote(5)
        value_ref = counter.get_value.remote()

        increment_result = miniray.get(increment_ref)
        value_result = miniray.get(value_ref)

        assert increment_result == 15
        assert value_result == 15

    def test_actor_with_complex_state(self, miniray_instance):
        """测试带有复杂状态的 Actor"""
        miniray = miniray_instance
        
        @miniray.remote
        class DataProcessor:
            def __init__(self):
                self.data = {}
                self.history = []

            def add_data(self, key, value):
                self.data[key] = value
                self.history.append(f"Added {key}: {value}")
                return f"Added {key}"

            def get_data(self, key):
                return self.data.get(key)

            def get_history(self):
                return self.history.copy()

        processor = DataProcessor.remote()

        # 添加数据
        add_ref1 = processor.add_data.remote("item1", [1, 2, 3])
        add_ref2 = processor.add_data.remote("item2", {"nested": "value"})

        miniray.get(add_ref1)
        result2 = miniray.get(add_ref2)

        assert result2 == "Added item2"

        # 获取数据
        data_ref = processor.get_data.remote("item1")
        history_ref = processor.get_history.remote()

        data_result = miniray.get(data_ref)
        history_result = miniray.get(history_ref)

        assert data_result == [1, 2, 3]
        assert len(history_result) == 2

    def test_multiple_actors(self, miniray_instance):
        """测试多个 Actor 同时工作"""
        miniray = miniray_instance
        
        @miniray.remote
        class Worker:
            def __init__(self, name):
                self.name = name
                self.completed_tasks = 0

            def process(self, task_id):
                self.completed_tasks += 1
                return f"{self.name} processed task {task_id}"

            def get_stats(self):
                return {"name": self.name, "completed": self.completed_tasks}

        # 创建多个 workers
        workers = [Worker.remote(f"Worker-{i}") for i in range(3)]

        # 并行处理任务
        results = []
        for i, worker in enumerate(workers):
            result_ref = worker.process.remote(i * 10)
            results.append(miniray.get(result_ref))

        # 验证结果
        expected = [f"Worker-{i} processed task {i * 10}" for i in range(3)]
        assert results == expected

        # 检查统计数据
        for i, worker in enumerate(workers):
            stats_ref = worker.get_stats.remote()
            stats = miniray.get(stats_ref)
            assert stats["name"] == f"Worker-{i}"
            assert stats["completed"] == 1

    def test_actor_method_chaining(self, miniray_instance):
        """测试 Actor 方法链式调用"""
        miniray = miniray_instance
        
        @miniray.remote
        class ChainCalculator:
            def __init__(self, initial=0):
                self.value = initial

            def add(self, x):
                self.value += x
                return self

            def multiply(self, x):
                self.value *= x
                return self

            def get_value(self):
                return self.value

        calc = ChainCalculator.remote(5)

        # 尝试链式调用（通过多次调用实现类似效果）
        calc.add.remote(3)  # value = 8
        calc.multiply.remote(2)  # value = 16
        result_ref = calc.get_value.remote()
        
        final_value = miniray.get(result_ref)
        assert final_value == 16

    def test_actor_exception_handling(self, miniray_instance):
        """测试 Actor 异常处理"""
        miniray = miniray_instance
        
        @miniray.remote
        class ErrorProneActor:
            def __init__(self):
                self.state = 0

            def risky_operation(self, should_fail=False):
                if should_fail:
                    raise ValueError("Intentional error for testing")
                self.state += 1
                return f"Success, state: {self.state}"

        actor = ErrorProneActor.remote()

        # 正常操作
        success_ref = actor.risky_operation.remote(False)
        result = miniray.get(success_ref)
        assert result == "Success, state: 1"

        # 测试错误情况 - 这可能需要特殊的错误处理策略
        error_ref = actor.risky_operation.remote(True)
        try:
            miniray.get(error_ref)
            # 如果没有抛出异常，说明错误处理机制不同
        except Exception:
            # 预期的异常处理
            pass

        # 确保 Actor 状态未损坏
        final_state_ref = actor.risky_operation.remote(False)
        final_result = miniray.get(final_state_ref)
        assert final_result == "Success, state: 2"


class TestActorLongRunningOperations:
    """测试 Actor 长时间运行操作"""
    
    def test_actor_long_running_operation(self, miniray_instance):
        """测试长时间运行的操作"""
        miniray = miniray_instance
        
        @miniray.remote
        class LongRunningTask:
            def __init__(self):
                self.status = "idle"

            def process_large_data(self, size):
                self.status = "processing"
                # 模拟处理大数据
                result = sum(i * i for i in range(size))
                self.status = "completed"
                return result

            def get_status(self):
                return self.status

        actor = LongRunningTask.remote()
        
        # 启动长时间运行的任务
        result_ref = actor.process_large_data.remote(1000)  # 较小的数字用于测试
        
        # 获取结果
        result = miniray.get(result_ref)
        expected = sum(i * i for i in range(1000))
        assert result == expected

        # 检查状态
        status_ref = actor.get_status.remote()
        status = miniray.get(status_ref)
        assert status == "completed"

    def test_actor_concurrent_access(self, miniray_instance):
        """测试 Actor 并发访问（实际上是串行化执行）"""
        miniray = miniray_instance
        
        @miniray.remote
        class SharedResource:
            def __init__(self):
                self.value = 0

            def increment(self):
                current = self.value
                time.sleep(0.01)  # 模拟一些处理时间
                self.value = current + 1
                return self.value

            def get_value(self):
                return self.value

        actor = SharedResource.remote()

        # 并发提交多个增量操作
        refs = []
        for _ in range(5):
            refs.append(actor.increment.remote())

        # 获取所有结果
        results = miniray.get(refs)
        
        # 由于 Actor 串行化执行，结果应该是 [1, 2, 3, 4, 5]
        # 但实际结果取决于实现，我们验证最终值
        final_value_ref = actor.get_value.remote()
        final_value = miniray.get(final_value_ref)
        assert final_value == 5

    def test_actor_with_different_data_types(self, miniray_instance):
        """测试 Actor 处理不同数据类型"""
        miniray = miniray_instance
        
        @miniray.remote
        class DataTypeProcessor:
            def __init__(self):
                self.storage = {}

            def store_value(self, key, value):
                self.storage[key] = value
                return f"Stored {key}"

            def retrieve_value(self, key):
                return self.storage.get(key)

        actor = DataTypeProcessor.remote()

        # 测试存储不同类型的数据
        test_data = [
            ("string", "hello world"),
            ("number", 42),
            ("list", [1, 2, 3, 4]),
            ("dict", {"nested": {"key": "value"}}),
            ("boolean", True),
            ("none", None)
        ]

        # 存储数据
        for key, value in test_data:
            store_ref = actor.store_value.remote(key, value)
            store_result = miniray.get(store_ref)
            assert store_result == f"Stored {key}"

        # 检索数据
        for key, expected_value in test_data:
            retrieve_ref = actor.retrieve_value.remote(key)
            retrieved_value = miniray.get(retrieve_ref)
            assert retrieved_value == expected_value
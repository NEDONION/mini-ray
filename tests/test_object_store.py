"""
ObjectStore 单元测试

使用 pytest 测试框架测试 C++ ObjectStore 的各项功能。

运行方式：
    pytest tests/test_object_store.py          # 运行本文件所有测试
    pytest tests/test_object_store.py -v       # 显示详细输出
    pytest tests/test_object_store.py -k put   # 只运行名称包含 'put' 的测试
"""
import pickle
import pytest


class TestObjectStoreBasic:
    """基础功能测试"""

    def test_create_object_store(self, core_module):
        """测试创建 ObjectStore"""
        store = core_module.ObjectStore()
        assert store is not None
        assert store.size() == 0

    def test_put_and_get(self, object_store):
        """测试存储和获取数据"""
        data = b"Hello, Mini-Ray!"
        ref = object_store.put(data)

        # 验证返回的是 ObjectRef
        assert ref is not None

        # 获取数据
        retrieved = object_store.get(ref)
        assert retrieved == data

    def test_put_increments_size(self, object_store):
        """测试 put 会增加 store 的大小"""
        initial_size = object_store.size()
        object_store.put(b"data1")
        assert object_store.size() == initial_size + 1

        object_store.put(b"data2")
        assert object_store.size() == initial_size + 2

    def test_contains(self, object_store):
        """测试 contains 方法"""
        data = b"test data"
        ref = object_store.put(data)

        # 对象应该存在
        assert object_store.contains(ref) is True

    def test_delete(self, object_store):
        """测试删除对象"""
        data = b"to be deleted"
        ref = object_store.put(data)

        # 删除前验证存在
        assert object_store.contains(ref) is True
        initial_size = object_store.size()

        # 删除
        object_store.delete(ref)

        # 删除后验证不存在
        assert object_store.contains(ref) is False
        assert object_store.size() == initial_size - 1


class TestObjectStorePythonObjects:
    """Python 对象序列化测试"""

    def test_store_python_dict(self, object_store):
        """测试存储 Python 字典"""
        data = {"name": "Mini-Ray", "version": "0.1.0"}
        serialized = pickle.dumps(data)

        ref = object_store.put(serialized)
        retrieved = pickle.loads(object_store.get(ref))

        assert retrieved == data

    def test_store_python_list(self, object_store):
        """测试存储 Python 列表"""
        data = [1, 2, 3, 4, 5]
        serialized = pickle.dumps(data)

        ref = object_store.put(serialized)
        retrieved = pickle.loads(object_store.get(ref))

        assert retrieved == data

    def test_store_complex_object(self, object_store):
        """测试存储复杂 Python 对象"""
        data = {
            "nested": {
                "list": [1, 2, 3],
                "dict": {"a": "b"}
            },
            "number": 42,
            "string": "test"
        }
        serialized = pickle.dumps(data)

        ref = object_store.put(serialized)
        retrieved = pickle.loads(object_store.get(ref))

        assert retrieved == data


class TestObjectStoreBatch:
    """批量操作测试"""

    def test_batch_put(self, object_store):
        """测试批量存储"""
        num_objects = 100
        refs = []

        for i in range(num_objects):
            data = pickle.dumps(f"Object {i}")
            ref = object_store.put(data)
            refs.append(ref)

        assert object_store.size() == num_objects
        assert len(refs) == num_objects

    def test_batch_get(self, object_store):
        """测试批量获取"""
        num_objects = 50
        expected_data = []
        refs = []

        # 批量存储
        for i in range(num_objects):
            data = f"Object {i}"
            expected_data.append(data)
            ref = object_store.put(pickle.dumps(data))
            refs.append(ref)

        # 批量获取并验证
        for i, ref in enumerate(refs):
            retrieved = pickle.loads(object_store.get(ref))
            assert retrieved == expected_data[i]

    def test_batch_delete(self, object_store):
        """测试批量删除"""
        num_objects = 30
        refs = []

        # 批量存储
        for i in range(num_objects):
            ref = object_store.put(pickle.dumps(i))
            refs.append(ref)

        assert object_store.size() == num_objects

        # 批量删除
        for ref in refs:
            object_store.delete(ref)
            assert not object_store.contains(ref)

        assert object_store.size() == 0


class TestObjectStoreEdgeCases:
    """边界情况测试"""

    def test_empty_data(self, object_store):
        """测试存储空数据"""
        empty_data = b""
        ref = object_store.put(empty_data)
        retrieved = object_store.get(ref)
        assert retrieved == empty_data

    def test_large_data(self, object_store):
        """测试存储大数据"""
        # 创建 10MB 的数据
        large_data = b"x" * (10 * 1024 * 1024)
        ref = object_store.put(large_data)
        retrieved = object_store.get(ref)
        assert len(retrieved) == len(large_data)

    def test_get_nonexistent_ref(self, object_store, core_module):
        """测试获取不存在的 ObjectRef"""
        # 创建一个从未存储过的 ref
        fake_ref = core_module.ObjectRef()

        # 应该抛出异常或返回 None（取决于实现）
        with pytest.raises(Exception):
            object_store.get(fake_ref)

    def test_delete_nonexistent_ref(self, object_store, core_module):
        """测试删除不存在的 ObjectRef（应该不报错）"""
        fake_ref = core_module.ObjectRef()
        # 删除不存在的对象不应该抛出异常
        object_store.delete(fake_ref)

    def test_duplicate_refs(self, object_store):
        """测试相同数据返回不同的 refs"""
        data = b"same data"
        ref1 = object_store.put(data)
        ref2 = object_store.put(data)

        # 即使数据相同，也应该返回不同的 refs
        assert ref1 != ref2
        assert object_store.size() == 2


class TestObjectStoreIntegration:
    """集成测试：模拟真实使用场景"""

    def test_function_result_storage(self, object_store):
        """模拟存储函数返回值"""
        def compute(x, y):
            return x ** 2 + y ** 2

        # 执行函数
        result = compute(3, 4)
        expected = 25

        # 序列化并存储
        ref = object_store.put(pickle.dumps(result))

        # 获取并验证
        retrieved = pickle.loads(object_store.get(ref))
        assert retrieved == expected

    def test_multiple_workers_simulation(self, object_store):
        """模拟多个 worker 存储结果"""
        # 模拟 3 个 worker 各自计算并存储结果
        worker_results = [
            {"worker_id": 0, "result": 10},
            {"worker_id": 1, "result": 20},
            {"worker_id": 2, "result": 30},
        ]

        refs = []
        for result in worker_results:
            ref = object_store.put(pickle.dumps(result))
            refs.append(ref)

        # 主进程获取所有结果
        retrieved_results = []
        for ref in refs:
            result = pickle.loads(object_store.get(ref))
            retrieved_results.append(result)

        assert retrieved_results == worker_results

    def test_data_pipeline(self, object_store):
        """模拟数据处理流水线"""
        # Stage 1: 原始数据
        raw_data = [1, 2, 3, 4, 5]
        ref1 = object_store.put(pickle.dumps(raw_data))

        # Stage 2: 处理数据（乘以2）
        data = pickle.loads(object_store.get(ref1))
        processed = [x * 2 for x in data]
        ref2 = object_store.put(pickle.dumps(processed))

        # Stage 3: 聚合数据（求和）
        data = pickle.loads(object_store.get(ref2))
        result = sum(data)
        ref3 = object_store.put(pickle.dumps(result))

        # 验证最终结果
        final = pickle.loads(object_store.get(ref3))
        assert final == 30  # (1+2+3+4+5) * 2 = 30


# 如果直接运行此文件，使用 pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

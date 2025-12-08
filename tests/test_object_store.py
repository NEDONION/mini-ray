"""
对象存储测试

测试 ObjectStore 的基本功能，适配 Free List 优化后 C++ 接口。
"""

import pytest
import pickle
# 假设 miniray._miniray_core 模块已正确配置路径并导入
import miniray._miniray_core as core

# 假设您已在 conftest.py 或测试文件中定义了 temp_object_store fixture，
# 它负责创建和清理 ObjectStore 实例。
# 例如：
# @pytest.fixture
# def temp_object_store():
#     store = core.ObjectStore(create=True)
#     yield store
#     core.cleanup_shared_memory() # 确保测试后清理共享内存


class TestObjectStore:
    """ObjectStore 测试类"""

    def test_create_object_store(self, temp_object_store):
        """测试创建 ObjectStore"""
        store = temp_object_store
        assert store.size() == 0, "新创建的 ObjectStore 应该为空"

    def test_put_and_get_bytes(self, temp_object_store):
        """测试存储和获取字节数据"""
        store = temp_object_store
        data = b"Hello, Mini-Ray!"
        ref = store.put(data)

        # 核心修改：store.get(ref) 返回 Buffer，需要调用 .data()
        buffer = store.get(ref)
        retrieved = buffer.data()

        assert isinstance(retrieved, bytes), "获取的数据类型应该是 bytes"
        assert retrieved == data, "获取的数据应该与存储的数据一致"

    def test_put_and_get_python_object(self, temp_object_store):
        """测试存储和获取 Python 对象"""
        store = temp_object_store
        python_data = {"result": 42, "status": "success", "data": [1, 2, 3]}
        serialized = pickle.dumps(python_data)
        ref = store.put(serialized)

        # 核心修改：store.get(ref) 返回 Buffer
        buffer = store.get(ref)
        retrieved_serialized = buffer.data() # 获取 bytes

        retrieved_data = pickle.loads(retrieved_serialized)
        assert retrieved_data == python_data, "反序列化的对象应该与原对象一致"

    def test_multiple_objects(self, temp_object_store):
        """测试批量存储和获取对象（同时验证 Free List 重用）"""
        store = temp_object_store
        refs = []

        # 存储多个对象
        for i in range(10):
            data = pickle.dumps(f"Object {i}")
            ref = store.put(data)
            refs.append(ref)

        assert store.size() == 10, "应该存储了 10 个对象"

        # 获取所有对象
        for i, ref in enumerate(refs):
            # 核心修改：store.get(ref) 返回 Buffer
            buffer = store.get(ref)
            data = pickle.loads(buffer.data())
            assert data == f"Object {i}", f"对象 {i} 应该匹配"

    def test_contains(self, temp_object_store):
        """测试检查对象是否存在"""
        store = temp_object_store
        data = b"test data"
        ref = store.put(data)

        assert store.contains(ref), "对象应该存在"

    def test_delete_and_reuse(self, temp_object_store):
        """测试删除对象和内存重用 (验证 Free List 核心功能)"""
        store = temp_object_store

        # 1. 存储一个大对象
        large_data = b"A" * 1024 * 1024 # 1MB
        ref_large = store.put(large_data)
        initial_size = store.size()

        # 2. 删除大对象 (空间被归还给 Free List)
        store.delete(ref_large)
        assert not store.contains(ref_large), "大对象应该已被删除"
        assert store.size() == initial_size - 1, "ObjectStore 大小应该减 1"

        # 3. 存储多个小对象，它们应该重用被释放的 1MB 空间
        refs_small = []
        small_data = b"b" * 1024 * 10 # 10KB
        for _ in range(50): # 应该轻松装入 1MB 空间
            refs_small.append(store.put(small_data))

        assert store.size() == initial_size - 1 + 50, "ObjectStore 大小应该增加 50"

        # 验证 Get 仍然有效
        for ref in refs_small:
            buffer = store.get(ref)
            assert buffer.data() == small_data

    def test_object_ref_equality(self):
        """测试 ObjectRef 的相等性"""
        # 注意：ObjectRef 默认构造函数可能生成 Nil ID，但 FromRandom 保证不同
        ref1 = core.ObjectRef.from_hex("00"*16)
        ref2 = core.ObjectRef.from_hex("00"*16)
        ref3 = core.ObjectRef.from_hex("01"*16)

        # 相同的 ID 应该相等
        assert ref1 == ref2
        # 不同的 ID 应该不相等
        assert ref1 != ref3

    def test_object_ref_hex(self):
        """测试 ObjectRef 的十六进制表示"""
        ref = core.ObjectRef.from_hex("FF" * 16)
        hex_str = ref.to_hex()

        assert isinstance(hex_str, str), "to_hex 应该返回字符串"
        assert len(hex_str) == 32, "十六进制字符串长度应该为 32"
        assert hex_str == "ff" * 16, "十六进制内容应该正确"
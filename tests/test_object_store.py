"""
对象存储测试

测试 ObjectStore 的基本功能
"""

import pytest
import pickle
import miniray._miniray_core as core


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

        retrieved = store.get(ref)
        assert retrieved == data, "获取的数据应该与存储的数据一致"

    def test_put_and_get_python_object(self, temp_object_store):
        """测试存储和获取 Python 对象"""
        store = temp_object_store
        python_data = {"result": 42, "status": "success", "data": [1, 2, 3]}
        serialized = pickle.dumps(python_data)
        ref = store.put(serialized)

        retrieved_serialized = store.get(ref)
        retrieved_data = pickle.loads(retrieved_serialized)
        assert retrieved_data == python_data, "反序列化的对象应该与原对象一致"

    def test_multiple_objects(self, temp_object_store):
        """测试批量存储和获取对象"""
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
            data = pickle.loads(store.get(ref))
            assert data == f"Object {i}", f"对象 {i} 应该匹配"

    def test_contains(self, temp_object_store):
        """测试检查对象是否存在"""
        store = temp_object_store
        data = b"test data"
        ref = store.put(data)

        assert store.contains(ref), "对象应该存在"

    def test_delete(self, temp_object_store):
        """测试删除对象"""
        store = temp_object_store
        data = b"test data"
        ref = store.put(data)

        initial_size = store.size()
        store.delete(ref)

        assert not store.contains(ref), "对象应该已被删除"
        assert store.size() == initial_size - 1, "ObjectStore 大小应该减 1"

    def test_object_ref_equality(self):
        """测试 ObjectRef 的相等性"""
        ref1 = core.ObjectRef()
        ref2 = core.ObjectRef()

        # 不同的 ObjectRef 不应该相等
        assert ref1 != ref2

        # 相同的 ObjectRef 应该相等
        assert ref1 == ref1

    def test_object_ref_hex(self):
        """测试 ObjectRef 的十六进制表示"""
        ref = core.ObjectRef()
        hex_str = ref.to_hex()

        assert isinstance(hex_str, str), "to_hex 应该返回字符串"
        assert len(hex_str) > 0, "十六进制字符串不应该为空"

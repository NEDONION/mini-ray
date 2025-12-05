"""
pybind11 绑定测试

测试 C++ 类到 Python 的绑定是否正确：
- ObjectID
- ObjectRef
- TaskSpec
- Task

运行方式：
    pytest tests/test_bindings.py -v
"""
import pytest


class TestObjectID:
    """ObjectID 绑定测试"""

    def test_create_object_id(self, core_module):
        """测试创建 ObjectID"""
        obj_id = core_module.ObjectID.from_random()
        assert obj_id is not None

    def test_object_id_uniqueness(self, core_module):
        """测试 ObjectID 的唯一性"""
        id1 = core_module.ObjectID.from_random()
        id2 = core_module.ObjectID.from_random()

        # 两个随机 ID 应该不相等
        assert id1 != id2

    def test_object_id_to_hex(self, core_module):
        """测试 ObjectID 转换为 hex 字符串"""
        obj_id = core_module.ObjectID.from_random()
        hex_str = obj_id.to_hex()

        # hex 字符串应该是 32 字符（16 字节 * 2）
        assert isinstance(hex_str, str)
        assert len(hex_str) == 32
        # 应该只包含 hex 字符
        assert all(c in '0123456789abcdef' for c in hex_str.lower())

    def test_object_id_hashable(self, core_module):
        """测试 ObjectID 可以作为字典的键"""
        id1 = core_module.ObjectID.from_random()
        id2 = core_module.ObjectID.from_random()

        # 应该可以 hash
        hash1 = hash(id1)
        hash2 = hash(id2)

        # 不同的 ID 应该有不同的 hash（大概率）
        assert hash1 != hash2

        # 可以作为字典的键
        d = {id1: "value1", id2: "value2"}
        assert d[id1] == "value1"
        assert d[id2] == "value2"

    def test_object_id_equality(self, core_module):
        """测试 ObjectID 的相等性"""
        id1 = core_module.ObjectID.from_random()
        id2 = core_module.ObjectID.from_random()

        # 自己应该等于自己
        assert id1 == id1
        assert id2 == id2

        # 不同的 ID 不应该相等
        assert id1 != id2

    def test_object_id_repr(self, core_module):
        """测试 ObjectID 的字符串表示"""
        obj_id = core_module.ObjectID.from_random()
        repr_str = repr(obj_id)

        # 应该有可读的字符串表示
        assert isinstance(repr_str, str)
        assert len(repr_str) > 0


class TestObjectRef:
    """ObjectRef 绑定测试"""

    def test_create_object_ref(self, core_module):
        """测试创建 ObjectRef"""
        ref = core_module.ObjectRef()
        assert ref is not None

    def test_object_ref_uniqueness(self, core_module):
        """测试 ObjectRef 的唯一性"""
        ref1 = core_module.ObjectRef()
        ref2 = core_module.ObjectRef()

        # 两个 ref 应该不相等
        assert ref1 != ref2

    def test_object_ref_from_object_id(self, core_module):
        """测试从 ObjectID 创建 ObjectRef"""
        obj_id = core_module.ObjectID.from_random()
        ref = core_module.ObjectRef(obj_id)

        # 应该能获取到相同的 ObjectID
        assert ref.get_object_id() == obj_id

    def test_object_ref_get_object_id(self, core_module):
        """测试获取 ObjectRef 的 ObjectID"""
        ref = core_module.ObjectRef()
        obj_id = ref.get_object_id()

        assert obj_id is not None
        assert isinstance(obj_id.to_hex(), str)

    def test_object_ref_hashable(self, core_module):
        """测试 ObjectRef 可以作为字典的键"""
        ref1 = core_module.ObjectRef()
        ref2 = core_module.ObjectRef()

        # 应该可以 hash
        hash1 = hash(ref1)
        hash2 = hash(ref2)

        # 不同的 ref 应该有不同的 hash
        assert hash1 != hash2

        # 可以作为字典的键
        d = {ref1: "value1", ref2: "value2"}
        assert d[ref1] == "value1"
        assert d[ref2] == "value2"

    def test_object_ref_equality(self, core_module):
        """测试 ObjectRef 的相等性"""
        ref1 = core_module.ObjectRef()
        ref2 = core_module.ObjectRef()

        # 自己应该等于自己
        assert ref1 == ref1
        assert ref2 == ref2

        # 不同的 ref 不应该相等
        assert ref1 != ref2

    def test_object_ref_repr(self, core_module):
        """测试 ObjectRef 的字符串表示"""
        ref = core_module.ObjectRef()
        repr_str = repr(ref)

        # 应该有可读的字符串表示
        assert isinstance(repr_str, str)
        assert len(repr_str) > 0


class TestTaskSpec:
    """TaskSpec 绑定测试"""

    def test_create_task_spec(self, core_module):
        """测试创建 TaskSpec"""
        task_spec = core_module.TaskSpec()
        assert task_spec is not None

    def test_task_spec_has_task_id(self, core_module):
        """测试 TaskSpec 有 task_id"""
        task_spec = core_module.TaskSpec()
        task_id = task_spec.task_id

        assert task_id is not None
        # task_id 应该是 ObjectID 类型
        assert hasattr(task_id, 'to_hex')

    def test_task_spec_has_function_id(self, core_module):
        """测试 TaskSpec 有 function_id"""
        task_spec = core_module.TaskSpec()
        function_id = task_spec.function_id

        assert function_id is not None
        # function_id 应该是 ObjectID 类型
        assert hasattr(function_id, 'to_hex')

    def test_task_spec_serialized_function(self, core_module):
        """测试 TaskSpec 的 serialized_function 属性"""
        task_spec = core_module.TaskSpec()

        # 设置序列化的函数
        data = [1, 2, 3, 4, 5]
        task_spec.serialized_function = data

        # 验证可以读取
        assert task_spec.serialized_function == data

    def test_task_spec_serialized_args(self, core_module):
        """测试 TaskSpec 的 serialized_args 属性"""
        task_spec = core_module.TaskSpec()

        # 设置序列化的参数
        args = [6, 7, 8, 9, 10]
        task_spec.serialized_args = args

        # 验证可以读取
        assert task_spec.serialized_args == args

    def test_task_spec_full_workflow(self, core_module):
        """测试 TaskSpec 的完整工作流"""
        import pickle

        # 创建一个模拟的函数
        def add(a, b):
            return a + b

        # 序列化函数和参数
        serialized_func = pickle.dumps(add)
        serialized_args = pickle.dumps((1, 2))

        # 创建 TaskSpec
        task_spec = core_module.TaskSpec()
        task_spec.serialized_function = list(serialized_func)
        task_spec.serialized_args = list(serialized_args)

        # 验证可以反序列化
        func = pickle.loads(bytes(task_spec.serialized_function))
        args = pickle.loads(bytes(task_spec.serialized_args))

        # 执行函数
        result = func(*args)
        assert result == 3


class TestTask:
    """Task 绑定测试"""

    def test_create_task(self, core_module):
        """测试创建 Task"""
        task = core_module.Task()
        assert task is not None

    def test_task_has_return_ref(self, core_module):
        """测试 Task 有 return_ref"""
        task = core_module.Task()
        return_ref = task.return_ref

        assert return_ref is not None
        # return_ref 应该是 ObjectRef 类型
        assert hasattr(return_ref, 'get_object_id')

    def test_task_from_task_spec(self, core_module):
        """测试从 TaskSpec 创建 Task"""
        task_spec = core_module.TaskSpec()
        task = core_module.Task(task_spec)

        assert task is not None
        # Task 应该包含相同的 TaskSpec
        assert task.task_spec.task_id == task_spec.task_id


class TestBindingInteraction:
    """测试不同绑定类之间的交互"""

    def test_object_ref_and_object_store(self, core_module):
        """测试 ObjectRef 和 ObjectStore 的交互"""
        store = core_module.ObjectStore()
        data = b"test data"

        # put 返回 ObjectRef
        ref = store.put(data)
        assert isinstance(ref, core_module.ObjectRef)

        # ObjectRef 可以用于 get
        retrieved = store.get(ref)
        assert retrieved == data

    def test_object_id_persistence(self, core_module):
        """测试 ObjectID 在多次操作中保持一致"""
        ref = core_module.ObjectRef()
        id1 = ref.get_object_id()
        id2 = ref.get_object_id()

        # 多次获取应该返回相同的 ObjectID
        assert id1 == id2
        assert id1.to_hex() == id2.to_hex()

    def test_task_spec_and_task_consistency(self, core_module):
        """测试 TaskSpec 和 Task 的一致性"""
        # 创建 TaskSpec
        task_spec = core_module.TaskSpec()
        original_task_id = task_spec.task_id

        # 从 TaskSpec 创建 Task
        task = core_module.Task(task_spec)

        # Task 中的 TaskSpec 应该有相同的 task_id
        assert task.task_spec.task_id == original_task_id


# 如果直接运行此文件，使用 pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

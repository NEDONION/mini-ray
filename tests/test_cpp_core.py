"""
测试 C++ 核心模块（旧版，保留用于手动运行）

⚠️ 注意：这是旧版测试文件，使用简单的函数而非 pytest 框架。

推荐使用新的 pytest 测试：
  - test_object_store.py: ObjectStore 功能测试
  - test_bindings.py: pybind11 绑定测试

运行方式：
  - 旧版（本文件）：python3 tests/test_cpp_core.py
  - 新版（推荐）：pytest tests/ -v

这个文件会验证 pybind11 绑定是否正常工作，包括所有 C++ 类。
"""
import sys
import os

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 添加 python/miniray 目录到路径（_miniray_core.so 在这里）
MINI_RAY_DIR = os.path.join(PROJECT_ROOT, 'python', 'miniray')
if MINI_RAY_DIR not in sys.path:
    sys.path.insert(0, MINI_RAY_DIR)


def test_import_core():
    """测试能否导入 C++ 核心模块"""
    try:
        import _miniray_core as core
        print(f"✓ 成功导入 C++ 核心模块，版本: {core.__version__}")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_object_id():
    """测试 ObjectID"""
    import _miniray_core as core

    # 创建随机 ObjectID
    id1 = core.ObjectID.from_random()
    id2 = core.ObjectID.from_random()

    print(f"ObjectID 1: {id1}")
    print(f"ObjectID 2: {id2}")

    # 测试不相等
    assert id1 != id2, "两个随机 ObjectID 应该不相等"

    # 测试转换为 hex
    hex_str = id1.to_hex()
    print(f"ObjectID hex: {hex_str}")
    assert len(hex_str) == 32, "ObjectID hex 应该是 32 字符（16 字节）"

    # 测试 hash
    _ = hash(id1)

    print("✓ ObjectID 测试通过")


def test_object_ref():
    """测试 ObjectRef"""
    import _miniray_core as core

    # 创建 ObjectRef
    ref1 = core.ObjectRef()
    ref2 = core.ObjectRef()

    print(f"ObjectRef 1: {ref1}")
    print(f"ObjectRef 2: {ref2}")

    # 测试不相等
    assert ref1 != ref2, "两个 ObjectRef 应该不相等"

    # 测试 hash
    _ = hash(ref1)

    # 测试从 ObjectID 创建
    obj_id = core.ObjectID.from_random()
    ref3 = core.ObjectRef(obj_id)
    assert ref3.get_object_id() == obj_id

    print("✓ ObjectRef 测试通过")


def test_object_store():
    """测试 ObjectStore"""
    import _miniray_core as core

    # 创建 ObjectStore
    store = core.ObjectStore()
    print(f"创建 ObjectStore，当前大小: {store.size()}")

    # 测试 Put 和 Get
    data = b"Hello, Mini-Ray!"
    ref = store.put(data)
    print(f"存储数据，ObjectRef: {ref}")

    # 检查是否存在
    assert store.contains(ref), "对象应该存在于 store 中"
    assert store.size() == 1, "Store 大小应该为 1"

    # 获取数据
    retrieved_data = store.get(ref)
    print(f"获取数据: {retrieved_data}")
    assert retrieved_data == data, "获取的数据应该与存储的数据一致"

    # 测试多个对象
    ref2 = store.put(b"Second object")
    ref3 = store.put(b"Third object")
    assert store.size() == 3, "Store 应该有 3 个对象"

    # 测试删除
    store.delete(ref2)
    assert not store.contains(ref2), "删除后对象不应该存在"
    assert store.size() == 2, "删除后 Store 大小应该为 2"

    print("✓ ObjectStore 测试通过")


def test_task_spec():
    """测试 TaskSpec"""
    import _miniray_core as core

    # 创建 TaskSpec
    task_spec = core.TaskSpec()
    print(f"TaskSpec task_id: {task_spec.task_id}")
    print(f"TaskSpec function_id: {task_spec.function_id}")

    # 设置序列化数据
    task_spec.serialized_function = [1, 2, 3, 4, 5]
    task_spec.serialized_args = [6, 7, 8, 9, 10]

    assert len(task_spec.serialized_function) == 5
    assert len(task_spec.serialized_args) == 5

    print("✓ TaskSpec 测试通过")


def test_task():
    """测试 Task"""
    import _miniray_core as core

    # 创建 Task
    task = core.Task()
    print(f"Task return_ref: {task.return_ref}")

    # 从 TaskSpec 创建
    task_spec = core.TaskSpec()
    task2 = core.Task(task_spec)
    assert task2.task_spec.task_id == task_spec.task_id

    print("✓ Task 测试通过")


def test_integration():
    """集成测试：模拟完整的存储-获取流程"""
    import _miniray_core as core
    import pickle

    print("\n=== 集成测试：模拟 Python 函数存储和获取 ===")

    # 创建 ObjectStore
    store = core.ObjectStore()

    # 模拟存储一个 Python 函数的返回值
    def add(a, b):
        return a + b

    result = add(1, 2)
    serialized_result = pickle.dumps(result)

    # 存储到 ObjectStore
    ref = store.put(serialized_result)
    print(f"存储函数返回值 {result}，ObjectRef: {ref}")

    # 获取并反序列化
    retrieved_data = store.get(ref)
    deserialized_result = pickle.loads(retrieved_data)
    print(f"获取并反序列化: {deserialized_result}")

    assert deserialized_result == result, "结果应该一致"
    print("✓ 集成测试通过")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("测试 Mini-Ray C++ 核心模块")
    print("=" * 60)

    if not test_import_core():
        print("\n✗ 导入模块失败，跳过其他测试")
        return False

    print("\n" + "-" * 60)
    print("测试 1: ObjectID")
    print("-" * 60)
    test_object_id()

    print("\n" + "-" * 60)
    print("测试 2: ObjectRef")
    print("-" * 60)
    test_object_ref()

    print("\n" + "-" * 60)
    print("测试 3: ObjectStore")
    print("-" * 60)
    test_object_store()

    print("\n" + "-" * 60)
    print("测试 4: TaskSpec")
    print("-" * 60)
    test_task_spec()

    print("\n" + "-" * 60)
    print("测试 5: Task")
    print("-" * 60)
    test_task()

    print("\n" + "-" * 60)
    print("测试 6: 集成测试")
    print("-" * 60)
    test_integration()

    print("\n" + "=" * 60)
    print("✓ 所有测试通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

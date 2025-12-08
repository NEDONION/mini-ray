#!/usr/bin/env python3
"""
示例 1: Phase 1 - 使用 C++ ObjectStore

这个示例展示如何使用 Phase 1 实现的 C++ ObjectStore：
1. 创建 ObjectStore
2. 存储和获取数据
3. 处理 Python 对象（通过 pickle）
4. 批量操作

适用阶段：Phase 1（当前）
"""
import sys
import os

# 添加路径（让示例可以独立运行）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINI_RAY_DIR = os.path.join(PROJECT_ROOT, 'python', 'miniray')
sys.path.insert(0, MINI_RAY_DIR)

import pickle
import _miniray_core as core


def example_basic():
    """基础用法：存储和获取数据"""
    print("\n" + "=" * 60)
    print("示例 1: 基础用法")
    print("=" * 60)

    # 创建 ObjectStore
    store = core.ObjectStore()
    print(f"✓ ObjectStore 创建成功")

    # 存储字节数据
    data = b"Hello, Mini-Ray!"
    ref = store.put(data)
    print(f"✓ 存储数据: {data}")
    print(f"  ObjectRef: {ref}")

    # 获取数据
    retrieved_buffer = store.get(ref)
    retrieved = retrieved_buffer.data()  # Buffer.data() 返回 bytes
    print(f"✓ 获取数据: {retrieved}")

    assert data == retrieved, "数据应该一致"
    print("✓ 验证通过！")


def example_python_objects():
    """进阶用法：存储 Python 对象"""
    print("\n" + "=" * 60)
    print("示例 2: 存储 Python 对象")
    print("=" * 60)

    store = core.ObjectStore()

    # 存储字典
    data = {
        "name": "Mini-Ray",
        "version": "0.1.0",
        "features": ["ObjectStore", "Task", "Actor"]
    }

    # 序列化后存储
    serialized = pickle.dumps(data)
    ref = store.put(serialized)
    print(f"✓ 存储 Python 对象: {data}")

    # 获取并反序列化
    retrieved_buffer = store.get(ref)
    retrieved_serialized = retrieved_buffer.data()
    retrieved_data = pickle.loads(retrieved_serialized)
    print(f"✓ 获取 Python 对象: {retrieved_data}")

    assert data == retrieved_data, "对象应该一致"
    print("✓ 验证通过！")


def example_batch_operations():
    """批量操作：存储和获取多个对象"""
    print("\n" + "=" * 60)
    print("示例 3: 批量操作")
    print("=" * 60)

    store = core.ObjectStore()

    # 批量存储
    refs = []
    for i in range(10):
        data = pickle.dumps({
            "id": i,
            "value": i * 10,
            "name": f"Object-{i}"
        })
        ref = store.put(data)
        refs.append(ref)

    print(f"✓ 批量存储了 {len(refs)} 个对象")
    print(f"  ObjectStore 大小: {store.size()}")

    # 批量获取
    results = []
    for ref in refs:
        buffer = store.get(ref)
        data = pickle.loads(buffer.data())
        results.append(data)

    print(f"✓ 批量获取了 {len(results)} 个对象")

    # 验证
    for i, obj in enumerate(results):
        assert obj["id"] == i
        assert obj["value"] == i * 10

    print("✓ 所有对象验证通过！")


def example_lifecycle():
    """对象生命周期：创建、检查、删除"""
    print("\n" + "=" * 60)
    print("示例 4: 对象生命周期管理")
    print("=" * 60)

    store = core.ObjectStore()

    # 创建对象
    data = pickle.dumps({"message": "This will be deleted"})
    ref = store.put(data)
    print(f"✓ 创建对象: {ref}")

    # 检查对象是否存在
    exists = store.contains(ref)
    print(f"✓ 对象存在: {exists}")
    assert exists, "对象应该存在"

    # 删除对象
    initial_size = store.size()
    store.delete(ref)
    print(f"✓ 删除对象")

    # 验证删除
    exists_after_delete = store.contains(ref)
    print(f"✓ 删除后对象存在: {exists_after_delete}")
    assert not exists_after_delete, "对象应该已被删除"
    assert store.size() == initial_size - 1, "大小应该减 1"

    print("✓ 生命周期管理验证通过！")


def example_real_world_simulation():
    """真实场景模拟：函数返回值存储"""
    print("\n" + "=" * 60)
    print("示例 5: 真实场景 - 模拟远程函数调用")
    print("=" * 60)

    store = core.ObjectStore()

    # 模拟一个计算函数
    def expensive_computation(x, y):
        """模拟一个耗时的计算"""
        return x ** 2 + y ** 2

    # 模拟远程调用：执行函数并存储结果
    print("\n模拟执行远程函数...")
    args_list = [(1, 2), (3, 4), (5, 6)]
    refs = []

    for args in args_list:
        # 执行函数
        result = expensive_computation(*args)

        # 序列化结果
        serialized_result = pickle.dumps(result)

        # 存储到 ObjectStore（模拟 Worker 存储结果）
        ref = store.put(serialized_result)
        refs.append(ref)

        print(f"  函数调用 expensive_computation{args} -> {result}")
        print(f"    存储为: {ref}")

    # 模拟主进程获取结果
    print("\n模拟主进程获取结果...")
    for i, ref in enumerate(refs):
        buffer = store.get(ref)
        result = pickle.loads(buffer.data())
        print(f"  结果 {i + 1}: {result}")

    print("\n✓ 远程函数调用模拟完成！")


def main():
    """运行所有示例"""
    print("\n" + "🚀 " * 20)
    print("Mini-Ray Phase 1 示例集合")
    print("展示如何使用 C++ ObjectStore")
    print("🚀 " * 20)

    try:
        example_basic()
        example_python_objects()
        example_batch_operations()
        example_lifecycle()
        example_real_world_simulation()

        print("\n" + "=" * 60)
        print("✅ 所有示例运行成功！")
        print("=" * 60)

        print("\n💡 提示：")
        print("  - Phase 1 已完成 ObjectStore 实现")
        print("  - Phase 2 将实现真正的远程函数调用")
        print("  - 敬请期待！")

    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

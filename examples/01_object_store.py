#!/usr/bin/env python3
"""
示例 1: 对象存储基础

演示如何使用 Mini-Ray 的对象存储功能
"""

import pickle
import miniray._miniray_core as core


def main():
    print("=" * 60)
    print("示例 1: 对象存储基础")
    print("=" * 60)

    # 1. 创建对象存储
    print("\n1. 创建 ObjectStore")
    store = core.ObjectStore(create=True)
    print(f"   ✓ ObjectStore 创建成功，当前对象数: {store.size()}")

    # 2. 存储简单字节数据
    print("\n2. 存储简单字节数据")
    data = b"Hello, Mini-Ray!"
    ref = store.put(data)
    print(f"   ✓ 存储数据: {data}")
    print(f"   ✓ ObjectRef: {ref}")

    # 3. 获取数据
    print("\n3. 获取数据")
    retrieved = store.get(ref)
    print(f"   ✓ 获取数据: {retrieved}")
    assert retrieved == data, "数据应该一致"

    # 4. 存储 Python 对象（通过 pickle）
    print("\n4. 存储 Python 对象")
    python_data = {
        "name": "Mini-Ray",
        "version": "0.1.0",
        "features": ["object_store", "scheduler", "distributed"]
    }
    serialized = pickle.dumps(python_data)
    ref2 = store.put(serialized)
    print(f"   ✓ 存储对象: {python_data}")

    # 5. 获取并反序列化
    print("\n5. 获取并反序列化")
    retrieved_serialized = store.get(ref2)
    retrieved_data = pickle.loads(retrieved_serialized)
    print(f"   ✓ 获取数据: {retrieved_data}")

    # 6. 检查对象是否存在
    print("\n6. 检查对象是否存在")
    print(f"   ✓ ref 存在: {store.contains(ref)}")
    print(f"   ✓ ref2 存在: {store.contains(ref2)}")
    print(f"   ✓ 当前对象数: {store.size()}")

    # 7. 删除对象
    print("\n7. 删除对象")
    store.delete(ref)
    print(f"   ✓ 删除 ref 后，存在: {store.contains(ref)}")
    print(f"   ✓ 当前对象数: {store.size()}")

    # 8. 清理
    print("\n8. 清理共享内存")
    core.cleanup_shared_memory()
    print("   ✓ 清理完成")

    print("\n" + "=" * 60)
    print("✓ 示例 1 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()

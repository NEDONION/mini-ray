#!/usr/bin/env python3
"""
Phase 1 验收测试：测试 C++ 核心模块

这个测试验证 C++ 实现的 ObjectStore 是否正常工作
"""
import sys
import os

# 获取项目根目录（test_phase1.py 所在目录）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# 添加 python/miniray 目录到路径（_miniray_core.so 在这里）
MINI_RAY_DIR = os.path.join(PROJECT_ROOT, 'python', 'miniray')
if MINI_RAY_DIR not in sys.path:
    sys.path.insert(0, MINI_RAY_DIR)

# 调试信息（可选，帮助定位问题）
print(f"项目根目录: {PROJECT_ROOT}")
print(f"Mini-Ray 目录: {MINI_RAY_DIR}")
print(f"模块路径已添加: {MINI_RAY_DIR in sys.path}")

import pickle
# 直接导入 C++ 模块（_miniray_core.so 在 python/miniray/ 目录下）
import _miniray_core as core

def main():
    print("=" * 60)
    print("Mini-Ray Phase 1 验收示例")
    print("=" * 60)

    # 1. 创建 ObjectStore
    print("\n1. 创建 ObjectStore")
    store = core.ObjectStore()
    print(f"   ✓ ObjectStore 创建成功，当前对象数: {store.size()}")

    # 2. 存储简单数据
    print("\n2. 存储简单数据")
    data = b"Hello, Mini-Ray from C++!"
    ref = store.put(data)
    print(f"   ✓ 存储数据: {data}")
    print(f"   ✓ ObjectRef: {ref}")

    # 3. 获取数据
    print("\n3. 获取数据")
    retrieved = store.get(ref)
    print(f"   ✓ 获取数据: {retrieved}")
    assert retrieved == data, "数据应该一致"

    # 4. 存储 Python 对象（通过 pickle）
    print("\n4. 存储 Python 对象（通过 pickle）")
    python_data = {"result": 42, "status": "success", "data": [1, 2, 3]}
    serialized = pickle.dumps(python_data)
    ref2 = store.put(serialized)
    print(f"   ✓ 存储 Python 对象: {python_data}")

    # 5. 获取并反序列化
    print("\n5. 获取并反序列化 Python 对象")
    retrieved_serialized = store.get(ref2)
    retrieved_python_data = pickle.loads(retrieved_serialized)
    print(f"   ✓ 获取数据: {retrieved_python_data}")
    assert retrieved_python_data == python_data, "Python 对象应该一致"

    # 6. 批量存储
    print("\n6. 批量存储多个对象")
    refs = []
    for i in range(10):
        data = pickle.dumps(f"Object {i}")
        ref = store.put(data)
        refs.append(ref)
    print(f"   ✓ 存储了 10 个对象，当前 ObjectStore 大小: {store.size()}")

    # 7. 批量获取
    print("\n7. 批量获取对象")
    for i, ref in enumerate(refs):
        data = pickle.loads(store.get(ref))
        assert data == f"Object {i}", f"对象 {i} 应该匹配"
    print(f"   ✓ 成功获取所有 {len(refs)} 个对象")

    # 8. 检查是否存在
    print("\n8. 检查对象是否存在")
    assert store.contains(ref), "对象应该存在"
    print(f"   ✓ 对象 {ref} 存在于 ObjectStore")

    # 9. 删除对象
    print("\n9. 删除对象")
    initial_size = store.size()
    store.delete(ref)
    assert not store.contains(ref), "对象应该已被删除"
    assert store.size() == initial_size - 1, "ObjectStore 大小应该减 1"
    print(f"   ✓ 成功删除对象，当前大小: {store.size()}")

    print("\n" + "=" * 60)
    print("✓ Phase 1 验收标准全部通过！")
    print("=" * 60)
    print("\n下一步：")
    print("  - Phase 2: 实现 Scheduler（C++ 调度器）")
    print("  - Phase 2: 实现 CoreWorker（C++ 核心工作组件）")
    print("  - Phase 2: 实现 Worker 进程和任务执行")

if __name__ == "__main__":
    main()

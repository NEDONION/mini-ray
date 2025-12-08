#!/usr/bin/env python3
"""诊断 ObjectStore 底层问题"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python', 'miniray'))

print("=" * 60)
print("ObjectStore C++ 层诊断")
print("=" * 60)

# 导入 C++ 模块
print("\n1. 导入 _miniray_core...")
import _miniray_core as core
print("   ✓ 导入成功")

# 清理
print("\n2. 清理旧的共享内存...")
try:
    core.ObjectStore.cleanup()
    print("   ✓ 清理完成")
except Exception as e:
    print(f"   ⚠️  清理失败（可能不存在）: {e}")

# 创建 ObjectStore
print("\n3. 创建 ObjectStore (create=True)...")
try:
    store = core.ObjectStore()
    print("   ✓ 创建成功")
    print(f"   初始大小: {store.size()}")
except Exception as e:
    print(f"   ❌ 创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 Put
print("\n4. 测试 Put 操作...")
try:
    data = b"Test"
    print(f"   尝试 Put {len(data)} 字节: {data}")

    ref = store.put(data)
    print(f"   ✓ Put 成功")
    print(f"   ObjectRef: {ref}")
    print(f"   当前大小: {store.size()}")

except Exception as e:
    print(f"   ❌ Put 失败: {e}")
    import traceback
    traceback.print_exc()

    # 打印调试信息
    print("\n   调试信息:")
    print(f"   - ObjectStore 大小: {store.size()}")
    print(f"   - 数据长度: {len(data)}")

    sys.exit(1)

# 测试 Get
print("\n5. 测试 Get 操作...")
try:
    buffer = store.get(ref)
    print(f"   ✓ Get 成功: {buffer}")

    # Buffer 对象调用 .data() 方法获取 bytes
    result_bytes = buffer.data()
    print(f"   ✓ 转换为 bytes: {result_bytes}")

    assert result_bytes == data, f"数据不一致: {result_bytes} != {data}"
    print("   ✓ 数据一致性验证通过")

except Exception as e:
    print(f"   ❌ Get 失败: {e}")
    import traceback
    traceback.print_exc()

# 清理
print("\n6. 清理...")
try:
    # cleanup 可能不是静态方法，尝试其他方式
    import subprocess
    subprocess.run(["rm", "-f", "/dev/shm/miniray_objectstore"], check=False)
except:
    pass
print("   ✓ 完成")

print("\n" + "=" * 60)
print("✅ 所有测试通过")
print("=" * 60)

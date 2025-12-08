#!/usr/bin/env python3
"""
示例 3: 简单任务执行

演示如何使用 CoreWorker 执行简单任务
"""

import pickle
import miniray._miniray_core as core


def fibonacci(n):
    """计算斐波那契数列的第 n 项"""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


def main():
    print("=" * 60)
    print("示例 3: 简单任务执行")
    print("=" * 60)

    # 1. 创建共享组件
    print("\n1. 创建 Scheduler 和 ObjectStore")
    scheduler = core.Scheduler(create=True)
    object_store = core.ObjectStore(create=True)
    print("   ✓ 组件创建成功")

    # 2. 创建 CoreWorker
    print("\n2. 创建 CoreWorker")
    worker = core.CoreWorker(scheduler, object_store, worker_id=0)
    print(f"   ✓ CoreWorker 创建成功 (ID: {worker.get_worker_id()})")

    # 3. 提交任务
    print("\n3. 提交任务: fibonacci(10)")
    task = core.Task()
    task.return_ref = core.ObjectRef()

    # 注意：这里假设 C++ Task 接口接受 list[int] (来自 list(bytes))
    task.serialized_function = list(pickle.dumps(fibonacci))
    task.serialized_args = list(pickle.dumps((10,)))

    return_ref = worker.submit_task(task)
    print(f"   ✓ 任务已提交")
    print(f"   ✓ 返回值 ObjectRef: {return_ref}")

    # 4. 模拟 Worker 获取并执行任务
    print("\n4. Worker 获取并执行任务")
    task_to_execute = worker.get_next_task()

    if task_to_execute:
        print("   ✓ 获取到任务")

        # 反序列化函数和参数
        # 注意：这里需要将 list[int] (C++ 返回) 转换回 bytes 才能反序列化
        func = pickle.loads(bytes(task_to_execute.serialized_function))
        args = pickle.loads(bytes(task_to_execute.serialized_args))

        # 执行任务
        result = func(*args)
        print(f"   ✓ 执行结果: fibonacci(10) = {result}")

        # 存储结果
        result_data = pickle.dumps(result)

        # 🟢 修复点 (第 64 行): put_object 期望 bytes，直接传入 result_data
        worker.put_object(task_to_execute.return_ref, result_data)
        print("   ✓ 结果已存储")

        # 获取结果 (假设 get_object 返回的是 Buffer，我们使用 .data() 提取 bytes)
        retrieved_result_data = worker.get_object(task_to_execute.return_ref)

        # 假设 get_object 返回 Buffer，我们需要提取 bytes
        data_bytes = retrieved_result_data.data() if hasattr(retrieved_result_data, 'data') else retrieved_result_data

        retrieved_result = pickle.loads(data_bytes)
        print(f"   ✓ 获取结果: {retrieved_result}")
    else:
        print("   ✗ 没有获取到任务")

    # 5. 清理
    print("\n5. 清理共享内存")
    core.cleanup_shared_memory()
    print("   ✓ 清理完成")

    print("\n" + "=" * 60)
    print("✓ 示例 3 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
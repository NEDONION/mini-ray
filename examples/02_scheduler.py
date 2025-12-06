#!/usr/bin/env python3
"""
示例 2: 调度器基础

演示如何使用 Mini-Ray 的调度器功能
"""

import pickle
import miniray._miniray_core as core


def square(x):
    """计算平方"""
    return x * x


def main():
    print("=" * 60)
    print("示例 2: 调度器基础")
    print("=" * 60)

    # 1. 创建调度器
    print("\n1. 创建 Scheduler")
    scheduler = core.Scheduler(create=True)
    print(f"   ✓ Scheduler 创建成功")
    print(f"   ✓ 待处理任务数: {scheduler.get_pending_task_count()}")

    # 2. 创建任务
    print("\n2. 创建任务")
    task = core.Task()
    task.return_ref = core.ObjectRef()
    task.serialized_function = list(pickle.dumps(square))
    task.serialized_args = list(pickle.dumps((5,)))
    print(f"   ✓ 任务创建: square(5)")
    print(f"   ✓ 返回值 ObjectRef: {task.return_ref}")

    # 3. 提交任务
    print("\n3. 提交任务")
    scheduler.submit_task(task)
    print(f"   ✓ 任务已提交")
    print(f"   ✓ 待处理任务数: {scheduler.get_pending_task_count()}")

    # 4. 获取任务
    print("\n4. 获取任务")
    retrieved_task = scheduler.get_next_task()
    if retrieved_task:
        print(f"   ✓ 获取到任务")
        print(f"   ✓ 返回值 ObjectRef: {retrieved_task.return_ref}")

        # 模拟执行任务
        func = pickle.loads(bytes(retrieved_task.serialized_function))
        args = pickle.loads(bytes(retrieved_task.serialized_args))
        result = func(*args)
        print(f"   ✓ 执行结果: {result}")
    else:
        print("   ✗ 没有获取到任务")

    # 5. Worker 管理
    print("\n5. Worker 管理")
    scheduler.register_worker(1)
    print(f"   ✓ 注册 Worker 1")
    print(f"   ✓ 空闲 Worker 数: {scheduler.get_idle_worker_count()}")

    scheduler.mark_worker_busy(1)
    print(f"   ✓ 标记 Worker 1 为忙碌")
    print(f"   ✓ 空闲 Worker 数: {scheduler.get_idle_worker_count()}")

    scheduler.mark_worker_idle(1)
    print(f"   ✓ 标记 Worker 1 为空闲")
    print(f"   ✓ 空闲 Worker 数: {scheduler.get_idle_worker_count()}")

    scheduler.unregister_worker(1)
    print(f"   ✓ 注销 Worker 1")
    print(f"   ✓ 空闲 Worker 数: {scheduler.get_idle_worker_count()}")

    # 6. 清理
    print("\n6. 清理共享内存")
    core.cleanup_shared_memory()
    print("   ✓ 清理完成")

    print("\n" + "=" * 60)
    print("✓ 示例 2 完成")
    print("=" * 60)


if __name__ == "__main__":
    main()

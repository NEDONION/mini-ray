#!/usr/bin/env python3
"""测试共享内存是否正常工作"""

import sys
import os
import time
import multiprocessing

sys.path.insert(0, 'python')
import miniray._miniray_core as core

def child_process():
    """子进程：打开共享内存并读取任务"""
    print(f"[Child] PID={os.getpid()}, 打开共享内存...", flush=True)

    try:
        scheduler = core.Scheduler(create=False)  # 打开已存在的
        print(f"[Child] 共享内存打开成功", flush=True)

        # 循环检查任务
        for i in range(10):
            count = scheduler.get_pending_task_count()
            print(f"[Child] 检查 {i}: 待处理任务数 = {count}", flush=True)

            if count > 0:
                task = scheduler.get_next_task()
                if task:
                    print(f"[Child] ✅ 获取到任务!", flush=True)
                    print(f"[Child]   - return_ref: {task.return_ref}", flush=True)
                    print(f"[Child]   - func_size: {len(task.serialized_function)}", flush=True)
                    print(f"[Child]   - args_size: {len(task.serialized_args)}", flush=True)
                    return

            time.sleep(0.5)

        print(f"[Child] ❌ 10次检查后仍未获取到任务", flush=True)

    except Exception as e:
        print(f"[Child] 错误: {e}", flush=True)
        import traceback
        traceback.print_exc()

def main():
    print("=" * 60)
    print("测试共享内存同步")
    print("=" * 60)

    # 1. 主进程创建共享内存和调度器
    print(f"\n[Main] PID={os.getpid()}, 创建共享内存...", flush=True)
    scheduler = core.Scheduler(create=True)
    object_store = core.ObjectStore(create=True)
    print(f"[Main] 共享内存创建成功", flush=True)

    # 2. 创建一个简单的任务
    print(f"\n[Main] 创建任务...", flush=True)
    task = core.Task()
    task.return_ref = core.ObjectRef()
    task.serialized_function = [1, 2, 3, 4, 5]  # 假数据
    task.serialized_args = [6, 7, 8]

    print(f"[Main] 提交任务...", flush=True)
    scheduler.submit_task(task)

    count = scheduler.get_pending_task_count()
    print(f"[Main] 任务已提交，待处理任务数 = {count}", flush=True)

    # 3. 启动子进程
    print(f"\n[Main] 启动子进程...", flush=True)
    p = multiprocessing.Process(target=child_process)
    p.start()

    # 4. 等待子进程
    p.join(timeout=10)

    if p.is_alive():
        print(f"\n[Main] ⚠️  子进程超时，强制终止", flush=True)
        p.terminate()
        p.join()
    else:
        print(f"\n[Main] 子进程已结束，退出码={p.exitcode}", flush=True)

    # 5. 清理
    print(f"\n[Main] 清理共享内存...", flush=True)
    core.cleanup_shared_memory()
    print(f"[Main] 完成", flush=True)

if __name__ == "__main__":
    main()

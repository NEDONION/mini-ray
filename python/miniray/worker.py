"""
worker.py - Worker 进程实现

============================================================
Python 语法和最佳实践
============================================================

1. class 和 __init__
   class: 定义类
   __init__: 构造函数，self 是实例引用
   最佳实践：用类封装相关状态和行为

2. 异常处理
   try/except: 捕获异常
   try/except/finally: 保证清理代码执行
   最佳实践：明确捕获特定异常类型

3. while 循环和主循环模式
   while running: 持续运行直到停止标志
   最佳实践：事件循环、后台服务常用模式

4. pickle 序列化
   loads(): 反序列化 bytes -> Python 对象
   dumps(): 序列化 Python 对象 -> bytes
   注意：bytes() 函数将 list 转为 bytes

5. *args 解包
   func(*args): 将元组解包为位置参数
   例如：func(*(1, 2)) 等价于 func(1, 2)

6. Optional 类型注解
   Optional[T]: 表示可能是 T 或 None
   等价于 Union[T, None]

7. traceback 错误追踪
   traceback.print_exc(): 打印完整异常堆栈
   最佳实践：调试时保留详细错误信息
"""

import sys
import os
import time
import traceback
from typing import Optional

# Try to use cloudpickle for better function serialization
# If not available, fall back to standard pickle
try:
    import cloudpickle as pickle
except ImportError:
    import pickle

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MINI_RAY_DIR = os.path.join(PROJECT_ROOT, 'python', 'miniray')
if MINI_RAY_DIR not in sys.path:
    sys.path.insert(0, MINI_RAY_DIR)

# Import core module from package to avoid duplicate registration
try:
    from . import _miniray_core as core
except ImportError as e:
    print(f"错误：无法导入 C++ 核心模块: {e}")
    print(f"请先编译：python3 setup.py build_ext --inplace")
    sys.exit(1)


class Worker:
    """
    Worker 类 - 封装 Worker 进程的逻辑

    职责：
    1. 初始化 CoreWorker
    2. 运行主循环
    3. 执行任务
    4. 错误处理
    """

    def __init__(self, worker_id: int, scheduler, object_store):
        """
        初始化 Worker

        类型注解：帮助理解参数类型
        """
        self.worker_id = worker_id
        self.scheduler = scheduler
        self.object_store = object_store

        self.core_worker = core.CoreWorker(
            scheduler,
            object_store,
            worker_id
        )

        self.running = False
        print(f"[Worker {worker_id}] 初始化完成", flush=True)

    def run(self):
        """
        Worker 主循环

        循环：获取任务 -> 执行 -> 存储结果 -> 重复
        """
        self.running = True
        print(f"[Worker {self.worker_id}] 开始运行...", flush=True)

        self.scheduler.register_worker(self.worker_id)
        print(f"[Worker {self.worker_id}] 已注册到 Scheduler", flush=True)

        try:
            while self.running:
                task = self._get_next_task()

                if task is not None:
                    self._execute_task(task)
                else:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\nWorker {self.worker_id} 收到中断信号")
        except Exception as e:
            print(f"Worker {self.worker_id} 发生错误: {e}")
            traceback.print_exc()
        finally:
            self.shutdown()

    def _get_next_task(self) -> Optional:
        """
        从 Scheduler 获取下一个任务

        返回 Task 或 None
        """
        self.core_worker.mark_worker_idle()
        task = self.core_worker.get_next_task()

        if task:
            print(f"[Worker {self.worker_id}] 获取到任务", flush=True)
            self.core_worker.mark_worker_busy()

        return task

    def _execute_task(self, task):
        """
        执行任务

        流程：反序列化 -> 执行 -> 序列化结果 -> 存储
        """
        try:
            """
            反序列化：
            task.serialized_function 是 C++ vector，pybind11 转为 Python list
            bytes(list) 将 list 转为 bytes，然后 pickle.loads 反序列化
            """
            print(f"[Worker {self.worker_id}] Task数据大小: func={len(task.serialized_function)}, args={len(task.serialized_args)}", flush=True)
            func = pickle.loads(bytes(task.serialized_function))
            args = pickle.loads(bytes(task.serialized_args))

            print(f"[Worker {self.worker_id}] 执行任务: {func.__name__}{args}", flush=True)

            """
            解包执行：func(*args) 将元组解包为位置参数
            """
            result = func(*args)
            print(f"[Worker {self.worker_id}] 任务结果: {result}", flush=True)

            """
            序列化：
            pickle.dumps() -> bytes
            list(bytes) -> [1, 2, 3] (C++ 期望 std::vector<uint8_t>)
            """
            serialized_result = pickle.dumps(result)
            result_bytes = list(serialized_result)

            self.core_worker.put_object(task.return_ref, result_bytes)
            print(f"[Worker {self.worker_id}] 结果已存储到 {task.return_ref}", flush=True)

        except Exception as e:
            print(f"Worker {self.worker_id} 执行任务失败: {e}")
            traceback.print_exc()

            error_result = pickle.dumps(e)
            self.core_worker.put_object(task.return_ref, list(error_result))

    def shutdown(self):
        """
        关闭 Worker

        清理：从 Scheduler 注销
        """
        if self.running:
            self.running = False
            self.scheduler.unregister_worker(self.worker_id)
            print(f"Worker {self.worker_id} 已关闭")


def worker_process(worker_id: int, scheduler=None, object_store=None):
    """
    Worker 进程入口函数

    multiprocessing.Process 的 target 函数
    每个进程有独立的内存空间，但通过共享内存访问相同的数据

    注意：Worker 进程不接受 scheduler 和 object_store 参数，
          而是自己打开已存在的共享内存（create=False）
    """
    # Worker 进程打开已存在的共享内存
    scheduler = core.Scheduler(create=False)
    object_store = core.ObjectStore(create=False)

    worker = Worker(worker_id, scheduler, object_store)
    worker.run()

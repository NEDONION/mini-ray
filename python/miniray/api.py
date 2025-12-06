"""
api.py - Mini-Ray 用户 API（Phase 2）

============================================================
Python 语法和最佳实践
============================================================

1. 装饰器（Decorator）
   语法：@decorator 修改函数行为
   实现：装饰器是返回函数的函数
   最佳实践：用于横切关注点（日志、缓存、权限等）

2. 全局变量和模块单例
   模块级变量在整个程序中只有一份
   多次 import 共享同一个实例
   最佳实践：用于全局状态管理

3. multiprocessing.Process
   创建新进程，独立内存空间
   daemon=True: 主进程退出时自动退出子进程
   最佳实践：CPU 密集型任务用多进程

4. pickle 序列化
   dumps(): Python 对象 -> bytes
   loads(): bytes -> Python 对象
   注意：可以序列化函数、类、数据

5. *args 和 **kwargs
   *args: 可变位置参数（元组）
   **kwargs: 可变关键字参数（字典）
   解包：func(*args) 将元组展开为参数

6. __call__ 特殊方法
   让对象可以像函数一样调用
   语法：obj() 等价于 obj.__call__()

7. 类型注解（Type Hints）
   语法：def func(x: int) -> str
   好处：提高可读性，支持 IDE 自动补全
   注意：运行时不强制检查
"""

import sys
import os
import multiprocessing
import time
from typing import Any, Callable, List, Union, Optional
import cloudpickle as pickle

# Set multiprocessing start method to 'fork' to avoid pickling C++ objects
# This must be done before any multiprocessing is used
try:
    multiprocessing.set_start_method('fork')
except RuntimeError:
    # Already set, ignore
    pass

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

from .worker import worker_process


# ============================================================
# 全局状态（单例模式）
# ============================================================

_global_scheduler: Optional['core.Scheduler'] = None
_global_object_store: Optional['core.ObjectStore'] = None
_global_core_worker: Optional['core.CoreWorker'] = None
_worker_processes: List[multiprocessing.Process] = []
_initialized: bool = False


# ============================================================
# 初始化和关闭
# ============================================================

def init(num_workers: int = 2):
    """
    初始化 Mini-Ray

    创建 Scheduler、ObjectStore、CoreWorker，启动 Worker 进程

    global 关键字：修改模块级全局变量
    """
    global _global_scheduler, _global_object_store, _global_core_worker
    global _worker_processes, _initialized

    if _initialized:
        print("⚠️  Mini-Ray 已经初始化")
        return

    print("=" * 60)
    print("🚀 Mini-Ray 初始化（Phase 2 - 共享内存版本）")
    print("=" * 60)

    # 主进程创建共享内存（create=True）
    _global_scheduler = core.Scheduler(create=True)
    _global_object_store = core.ObjectStore(create=True)
    print(f"✅ 创建 Scheduler 和 ObjectStore（共享内存）")

    _global_core_worker = core.CoreWorker(
        _global_scheduler,
        _global_object_store,
        worker_id=-1
    )
    print(f"✅ 创建主进程 CoreWorker")

    for worker_id in range(num_workers):
        _global_scheduler.register_worker(worker_id)

        # 不传递 scheduler 和 object_store，Worker 进程会自己打开共享内存
        p = multiprocessing.Process(
            target=worker_process,
            args=(worker_id,),
            daemon=True
        )
        p.start()
        _worker_processes.append(p)
        print(f"✅ 启动 Worker {worker_id} (PID: {p.pid})")

    _initialized = True
    print(f"✅ Mini-Ray 已启动（{num_workers} workers）")
    print("=" * 60)


def shutdown():
    """
    关闭 Mini-Ray

    停止所有 Worker 进程并清理全局变量
    """
    global _global_scheduler, _global_object_store, _global_core_worker
    global _worker_processes, _initialized

    if not _initialized:
        print("⚠️  Mini-Ray 未初始化")
        return

    print("\n" + "=" * 60)
    print("🛑 关闭 Mini-Ray")
    print("=" * 60)

    for worker_id, p in enumerate(_worker_processes):
        if p.is_alive():
            p.terminate()
            p.join(timeout=1.0)
            print(f"✅ Worker {worker_id} 已停止")

    # 清理共享内存
    try:
        core.cleanup_shared_memory()
        print("✅ 共享内存已清理")
    except Exception as e:
        print(f"⚠️  清理共享内存时出错: {e}")

    _global_scheduler = None
    _global_object_store = None
    _global_core_worker = None
    _worker_processes = []
    _initialized = False

    print("✅ Mini-Ray 已关闭")
    print("=" * 60)


# ============================================================
# 远程函数装饰器
# ============================================================

class RemoteFunction:
    """
    远程函数包装器

    设计模式：
    - Proxy 模式：作为函数的代理
    - Future 模式：返回 ObjectRef（未来的结果）

    装饰器原理：
    @remote 等价于 func = remote(func)
    """

    def __init__(self, func: Callable):
        """
        初始化远程函数

        __init__: Python 构造函数
        self: 实例引用（类似 C++ 的 this）
        """
        self.func = func
        self.func_name = func.__name__

    def remote(self, *args, **kwargs) -> 'core.ObjectRef':
        """
        远程调用函数

        工作流程：
        1. 创建 Task 对象
        2. 序列化函数和参数（pickle）
        3. 提交任务到 Scheduler
        4. 返回 ObjectRef
        """
        if not _initialized:
            raise RuntimeError("Mini-Ray 未初始化，请先调用 miniray.init()")

        if kwargs:
            raise NotImplementedError("暂不支持关键字参数")

        task = core.Task()

        """
        序列化流程：
        pickle.dumps(obj) -> bytes
        list(bytes) -> [128, 3, ...] (C++ 期望 std::vector<uint8_t>)
        """
        serialized_func = pickle.dumps(self.func)
        task.serialized_function = list(serialized_func)

        serialized_args = pickle.dumps(args)
        task.serialized_args = list(serialized_args)

        print(f"[DEBUG] 序列化大小: func={len(task.serialized_function)}, args={len(task.serialized_args)}", flush=True)
        print(f"[DEBUG] task对象类型: {type(task)}", flush=True)
        print(f"[DEBUG] task.serialized_function前10字节: {task.serialized_function[:10]}", flush=True)
        print(f"[DEBUG] task.serialized_args前10字节: {task.serialized_args[:10]}", flush=True)

        print(f"[Python] 调用 submit_task 之前...", flush=True)
        result_ref = _global_core_worker.submit_task(task)
        print(f"[Python] 调用 submit_task 之后, result_ref={result_ref}", flush=True)
        print(f"📤 提交任务: {self.func_name}{args} -> {result_ref}")

        return result_ref

    def __call__(self, *args, **kwargs):
        """
        直接调用（本地执行）

        __call__: 使对象可调用
        用法：add(1, 2) 直接返回结果，不是 ObjectRef
        """
        return self.func(*args, **kwargs)


def remote(func: Callable) -> RemoteFunction:
    """
    远程函数装饰器

    装饰器语法：
        @remote
        def func():
            pass

    等价于：
        func = remote(func)
    """
    return RemoteFunction(func)


# ============================================================
# 获取远程对象
# ============================================================

def _get_one_with_wait(object_ref: 'core.ObjectRef',
                       timeout_s: float = 10.0,
                       poll_interval: float = 0.01) -> Any:
    """
    阻塞等待单个 ObjectRef 的值可用：
    - 如果对象已经在 ObjectStore 里：立刻返回
    - 如果还没写进去：循环重试，直到超时
    """
    if not _initialized:
        raise RuntimeError("Mini-Ray 未初始化，请先调用 miniray.init()")

    deadline = None if timeout_s is None else (time.time() + timeout_s)
    last_err: Optional[Exception] = None

    while True:
        try:
            data = _global_core_worker.get_object(object_ref)
            result = pickle.loads(data)
            print(f"📥 获取结果: {object_ref} -> {result}")
            return result
        except RuntimeError as e:
            msg = str(e)
            # 只有 "Object not found" 说明 worker 还没写结果，可以重试
            if "Object not found" not in msg:
                # 其它错误直接抛
                raise

            last_err = e
            # 检查是否超时
            if deadline is not None and time.time() >= deadline:
                raise RuntimeError(
                    f"Timeout waiting for object: {object_ref.to_hex()}"
                ) from last_err

            # 还没超时，小睡一下再试
            time.sleep(poll_interval)


def get(object_refs: Union['core.ObjectRef', List['core.ObjectRef']],
        timeout_s: float = 10.0) -> Any:
    """
    获取远程对象的值（阻塞直到准备好）

    支持：
      - ray.get(ref)          -> 单个结果
      - ray.get([ref1, ref2]) -> 结果列表
    """
    if isinstance(object_refs, core.ObjectRef):
        # 单个 ObjectRef
        return _get_one_with_wait(object_refs, timeout_s=timeout_s)
    else:
        # 多个 ObjectRef
        results: List[Any] = []
        for ref in object_refs:
            result = _get_one_with_wait(ref, timeout_s=timeout_s)
            results.append(result)
        return results

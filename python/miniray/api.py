"""
Mini-Ray 用户 API
提供类似 Ray 的装饰器和函数接口
"""

from typing import Any, Callable, List, Union
from .core import ObjectRef
from .scheduler import Scheduler
from .actor import ActorClass


# 全局调度器实例
_global_scheduler: Scheduler = None


def init(num_workers: int = 4):
    """
    初始化 Mini-Ray

    Args:
        num_workers: Worker 进程数量

    Example:
        >>> import miniray
        >>> miniray.init(num_workers=4)
    """
    global _global_scheduler

    if _global_scheduler is not None:
        print("⚠️  Mini-Ray 已经初始化")
        return

    print("="*60)
    print("🚀 Mini-Ray 初始化")
    print("="*60)

    _global_scheduler = Scheduler(num_workers=num_workers)
    _global_scheduler.start()

    print(f"✅ Mini-Ray 已启动（{num_workers} workers）")
    print("="*60)


def shutdown():
    """
    关闭 Mini-Ray

    Example:
        >>> miniray.shutdown()
    """
    global _global_scheduler

    if _global_scheduler is None:
        print("⚠️  Mini-Ray 未初始化")
        return

    _global_scheduler.shutdown()
    _global_scheduler = None


def get(object_refs: Union[ObjectRef, List[ObjectRef]], timeout: float = None) -> Any:
    """
    获取对象值（阻塞）

    Args:
        object_refs: 单个或多个 ObjectRef
        timeout: 超时时间（秒）

    Returns:
        单个值或值列表

    Example:
        >>> ref = add.remote(1, 2)
        >>> result = miniray.get(ref)
        >>> print(result)  # 3

        >>> refs = [add.remote(i, i) for i in range(10)]
        >>> results = miniray.get(refs)
        >>> print(results)  # [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
    """
    global _global_scheduler

    if _global_scheduler is None:
        raise RuntimeError("Mini-Ray 未初始化，请先调用 miniray.init()")

    # 处理单个 ObjectRef
    if isinstance(object_refs, ObjectRef):
        return _global_scheduler.object_store.get(object_refs, timeout=timeout)

    # 处理多个 ObjectRef
    if isinstance(object_refs, list):
        return [
            _global_scheduler.object_store.get(ref, timeout=timeout)
            for ref in object_refs
        ]

    raise TypeError(f"不支持的类型: {type(object_refs)}")


class RemoteFunction:
    """
    远程函数包装器
    将普通函数转换为可以远程执行的函数
    """

    def __init__(self, func: Callable):
        self._func = func
        self.__name__ = func.__name__

    def remote(self, *args, **kwargs) -> ObjectRef:
        """
        远程执行函数

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            ObjectRef: 结果引用
        """
        global _global_scheduler

        if _global_scheduler is None:
            raise RuntimeError("Mini-Ray 未初始化，请先调用 miniray.init()")

        return _global_scheduler.submit_task(self._func, args, kwargs)

    def __call__(self, *args, **kwargs):
        """直接调用（本地执行）"""
        return self._func(*args, **kwargs)


def remote(func_or_class):
    """
    @miniray.remote 装饰器
    支持函数和类（Actor）

    Example:
        # 远程函数
        @miniray.remote
        def add(a, b):
            return a + b

        ref = add.remote(1, 2)
        result = miniray.get(ref)

        # Actor
        @miniray.remote
        class Counter:
            def __init__(self):
                self.value = 0

            def increment(self):
                self.value += 1
                return self.value

        counter = Counter.remote()
        result = miniray.get(counter.increment.remote())
    """
    # 判断是类还是函数
    if isinstance(func_or_class, type):
        # Actor（类）
        return ActorClass(func_or_class)
    else:
        # 远程函数
        return RemoteFunction(func_or_class)

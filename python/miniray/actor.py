"""
Mini-Ray Actor 实现
Actor 是有状态的对象，方法调用会被串行化执行
"""

import uuid
from typing import Any, Callable
from multiprocessing import Process, Queue, Manager

from .core import ObjectRef, ObjectStore


class ActorClass:
    """
    Actor 类包装器
    将普通类转换为 Actor 类
    """

    def __init__(self, cls: type):
        self._cls = cls
        self.__name__ = cls.__name__

    def remote(self, *args, **kwargs):
        """
        创建 Actor 实例

        Returns:
            ActorHandle: Actor 句柄
        """
        from .api import _global_scheduler

        if _global_scheduler is None:
            raise RuntimeError("Mini-Ray 未初始化，请先调用 miniray.init()")

        # 创建 Actor 进程
        actor_id = str(uuid.uuid4())
        actor_handle = ActorHandle(
            actor_id=actor_id,
            cls=self._cls,
            init_args=args,
            init_kwargs=kwargs,
            object_store=_global_scheduler.object_store
        )

        # 启动 Actor 进程
        actor_handle.start()

        return actor_handle


class ActorHandle:
    """
    Actor 句柄
    用于调用 Actor 的方法
    """

    def __init__(
        self,
        actor_id: str,
        cls: type,
        init_args: tuple,
        init_kwargs: dict,
        object_store: ObjectStore
    ):
        self.actor_id = actor_id
        self._cls = cls
        self._init_args = init_args
        self._init_kwargs = init_kwargs
        self._object_store = object_store

        # Actor 的方法调用队列
        manager = Manager()
        self._method_queue = Queue()
        self._store_dict = manager.dict()

        # Actor 进程
        self._process = None

    def start(self):
        """启动 Actor 进程"""
        self._process = Process(
            target=actor_worker_loop,
            args=(
                self.actor_id,
                self._cls,
                self._init_args,
                self._init_kwargs,
                self._method_queue,
                self._store_dict
            )
        )
        self._process.start()
        print(f"[Actor-{self.actor_id[:8]}] 启动")

    def __getattr__(self, method_name: str):
        """
        拦截方法调用

        Returns:
            ActorMethod: 方法包装器
        """
        # 避免无限递归
        if method_name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{method_name}'")

        return ActorMethod(
            actor_handle=self,
            method_name=method_name
        )

    def _submit_method_call(
        self,
        method_name: str,
        args: tuple,
        kwargs: dict
    ) -> ObjectRef:
        """提交方法调用到 Actor"""
        result_ref = ObjectRef(str(uuid.uuid4()))

        method_call = {
            'method_name': method_name,
            'args': args,
            'kwargs': kwargs,
            'result_ref': result_ref
        }

        self._method_queue.put(method_call)

        return result_ref

    def shutdown(self):
        """关闭 Actor"""
        self._method_queue.put(None)
        self._process.join(timeout=2.0)
        if self._process.is_alive():
            self._process.terminate()


class ActorMethod:
    """
    Actor 方法包装器
    """

    def __init__(self, actor_handle: ActorHandle, method_name: str):
        self._actor_handle = actor_handle
        self._method_name = method_name

    def remote(self, *args, **kwargs) -> ObjectRef:
        """远程调用方法"""
        return self._actor_handle._submit_method_call(
            self._method_name,
            args,
            kwargs
        )


def actor_worker_loop(
    actor_id: str,
    cls: type,
    init_args: tuple,
    init_kwargs: dict,
    method_queue: Queue,
    store_dict: dict
):
    """
    Actor Worker 主循环

    Args:
        actor_id: Actor ID
        cls: Actor 类
        init_args: 初始化位置参数
        init_kwargs: 初始化关键字参数
        method_queue: 方法调用队列
        store_dict: 共享对象存储
    """
    print(f"[Actor-{actor_id[:8]}] 初始化...")

    # 创建 Actor 实例
    actor_instance = cls(*init_args, **init_kwargs)

    object_store = ObjectStore(store_dict)

    print(f"[Actor-{actor_id[:8]}] 就绪，等待方法调用")

    while True:
        try:
            method_call = method_queue.get(timeout=0.1)

            if method_call is None:  # 终止信号
                print(f"[Actor-{actor_id[:8]}] 收到终止信号")
                break

            method_name = method_call['method_name']
            args = method_call['args']
            kwargs = method_call['kwargs']
            result_ref = method_call['result_ref']

            print(f"[Actor-{actor_id[:8]}] 调用方法: {method_name}")

            try:
                # 获取方法
                method = getattr(actor_instance, method_name)

                # 执行方法
                result = method(*args, **kwargs)

                # 存储结果
                store_dict[result_ref.object_id] = result

            except Exception as e:
                print(f"[Actor-{actor_id[:8]}] 方法调用失败: {e}")
                store_dict[result_ref.object_id] = e

        except Exception:
            # Queue.get() 超时，继续循环
            continue

    print(f"[Actor-{actor_id[:8]}] 关闭")

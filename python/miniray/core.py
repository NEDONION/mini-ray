"""
Mini-Ray 核心组件
包含：ObjectRef, Task, ObjectStore, Worker
"""

import uuid
import time
from dataclasses import dataclass
from typing import Any, Callable
from multiprocessing import Queue


@dataclass
class ObjectRef:
    """对象引用 - 表示远程对象的句柄（类似 Future）"""
    object_id: str

    def __repr__(self):
        return f"ObjectRef({self.object_id[:8]}...)"


@dataclass
class Task:
    """任务封装"""
    task_id: str
    func: Callable  # 序列化后的函数
    args: tuple
    kwargs: dict
    result_ref: ObjectRef

    def __repr__(self):
        return f"Task({self.task_id[:8]}..., func={self.func.__name__})"


class ObjectStore:
    """
    对象存储 - 存储任务结果
    使用 multiprocessing.Manager().dict() 实现跨进程共享
    """

    def __init__(self, store_dict):
        """
        Args:
            store_dict: multiprocessing.Manager().dict()
        """
        self._store = store_dict

    def put(self, value: Any) -> ObjectRef:
        """
        存储对象，返回对象引用

        Args:
            value: 要存储的值

        Returns:
            ObjectRef: 对象引用
        """
        object_id = str(uuid.uuid4())
        self._store[object_id] = value
        return ObjectRef(object_id)

    def get(self, object_ref: ObjectRef, timeout: float = None) -> Any:
        """
        获取对象值（阻塞直到对象可用）

        Args:
            object_ref: 对象引用
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            对象值

        Raises:
            TimeoutError: 超时
            KeyError: 对象不存在
        """
        start_time = time.time()

        while True:
            if object_ref.object_id in self._store:
                return self._store[object_ref.object_id]

            # 检查超时
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(
                        f"Timeout waiting for {object_ref}"
                    )

            # 短暂休眠，避免 CPU 空转
            time.sleep(0.001)

    def contains(self, object_ref: ObjectRef) -> bool:
        """检查对象是否存在"""
        return object_ref.object_id in self._store


def worker_loop(
    worker_id: int,
    task_queue: Queue,
    store_dict: dict,
    running_flag: dict
):
    """
    Worker 主循环 - 从队列获取任务并执行

    Args:
        worker_id: Worker ID
        task_queue: 任务队列
        store_dict: 共享对象存储字典
        running_flag: 运行标志（用于优雅关闭）
    """
    object_store = ObjectStore(store_dict)

    print(f"[Worker-{worker_id}] 启动")

    while running_flag.get('running', True):
        try:
            # 从队列获取任务（带超时，以便检查 running_flag）
            task = task_queue.get(timeout=0.1)

            if task is None:  # 终止信号
                print(f"[Worker-{worker_id}] 收到终止信号")
                break

            print(f"[Worker-{worker_id}] 执行任务: {task.task_id[:8]}...")

            try:
                # 执行任务
                result = task.func(*task.args, **task.kwargs)

                # 存储结果
                object_store._store[task.result_ref.object_id] = result

                print(f"[Worker-{worker_id}] 任务完成: {task.task_id[:8]}...")

            except Exception as e:
                # 存储异常
                print(f"[Worker-{worker_id}] 任务失败: {e}")
                object_store._store[task.result_ref.object_id] = e

        except Exception:
            # Queue.get() 超时，继续循环
            continue

    print(f"[Worker-{worker_id}] 关闭")

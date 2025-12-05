"""
Mini-Ray 调度器
负责任务调度和 Worker 管理
"""

import uuid
from multiprocessing import Process, Queue, Manager
from typing import Callable, List

from .core import Task, ObjectRef, ObjectStore, worker_loop


class Scheduler:
    """
    任务调度器
    - 管理 Worker 进程池
    - 调度任务到 Worker
    - 管理对象存储
    """

    def __init__(self, num_workers: int = 4):
        """
        Args:
            num_workers: Worker 进程数量
        """
        self.num_workers = num_workers

        # 使用 Manager 创建跨进程共享数据结构
        manager = Manager()

        # 任务队列
        self.task_queue = Queue()

        # 对象存储（共享字典）
        self._store_dict = manager.dict()
        self.object_store = ObjectStore(self._store_dict)

        # Worker 进程列表
        self.workers: List[Process] = []

        # 运行标志
        self._running_flag = manager.dict()
        self._running_flag['running'] = True

    def start(self):
        """启动 Worker 进程池"""
        print(f"🚀 启动 {self.num_workers} 个 Worker...")

        for i in range(self.num_workers):
            worker = Process(
                target=worker_loop,
                args=(i, self.task_queue, self._store_dict, self._running_flag)
            )
            worker.start()
            self.workers.append(worker)

        print(f"✅ 所有 Worker 已启动")

    def submit_task(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None
    ) -> ObjectRef:
        """
        提交任务到队列

        Args:
            func: 要执行的函数
            args: 位置参数
            kwargs: 关键字参数

        Returns:
            ObjectRef: 结果引用
        """
        if kwargs is None:
            kwargs = {}

        # 创建任务
        task_id = str(uuid.uuid4())
        result_ref = ObjectRef(str(uuid.uuid4()))

        task = Task(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            result_ref=result_ref
        )

        # 提交到队列
        self.task_queue.put(task)

        return result_ref

    def shutdown(self):
        """关闭调度器和所有 Worker"""
        print("\n👋 关闭 Mini-Ray...")

        # 设置停止标志
        self._running_flag['running'] = False

        # 发送终止信号给所有 Worker
        for _ in self.workers:
            self.task_queue.put(None)

        # 等待所有 Worker 结束
        for worker in self.workers:
            worker.join(timeout=2.0)
            if worker.is_alive():
                print(f"⚠️  Worker {worker.pid} 未正常退出，强制终止")
                worker.terminate()

        print("✅ Mini-Ray 已关闭")

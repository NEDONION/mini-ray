"""
Base Trainer - 通用训练框架基类

提供分布式训练的通用框架，管理 Mini-Ray 生命周期、Worker 创建、训练循环等
"""

from typing import List, Dict, Any, Optional
import time

import miniray


class BaseTrainer:
    """
    通用训练器基类

    职责：
    1. 管理 Mini-Ray 生命周期（init/shutdown）
    2. Worker 创建和管理
    3. 训练循环框架（epoch loop）
    4. 钩子方法（on_epoch_start, on_epoch_end 等）

    使用方式：
        继承此类，实现 create_worker() 方法，可选实现各种钩子方法
    """

    def __init__(self, num_workers: int = 4, auto_init: bool = True):
        """
        Args:
            num_workers: Worker 数量
            auto_init: 是否自动初始化 Mini-Ray（默认 True）
        """
        self.num_workers = num_workers
        self.auto_init = auto_init
        self.workers: Optional[List] = None
        self._miniray_initialized = False

    # ============================================================
    # 核心接口（子类必须实现）
    # ============================================================

    def create_worker(self, worker_id: int, **kwargs) -> Any:
        """
        创建单个 Worker（子类必须实现）

        Args:
            worker_id: Worker ID
            **kwargs: 额外参数

        Returns:
            Worker Actor 引用

        Examples:
            >>> def create_worker(self, worker_id, **kwargs):
            >>>     return MyWorker.remote(worker_id, **kwargs)
        """
        raise NotImplementedError("子类必须实现 create_worker() 方法")

    # ============================================================
    # 训练循环框架
    # ============================================================

    def train(self, epochs: int, **kwargs) -> Dict[str, Any]:
        """
        训练主循环

        Args:
            epochs: 训练轮数
            **kwargs: 传递给各个钩子的额外参数

        Returns:
            训练结果字典
        """
        # 1. 初始化 Mini-Ray
        if self.auto_init and not self._miniray_initialized:
            print(f"[BaseTrainer] 初始化 Mini-Ray ({self.num_workers} workers)...")
            miniray.init(num_workers=self.num_workers)
            self._miniray_initialized = True

        # 2. 创建 Workers
        print(f"[BaseTrainer] 创建 {self.num_workers} 个 Workers...")
        self.workers = self._create_workers(**kwargs)

        # 3. 训练前钩子
        self.on_train_start(**kwargs)

        # 4. 训练循环
        history = []
        for epoch in range(epochs):
            epoch_start_time = time.time()

            # Epoch 开始钩子
            self.on_epoch_start(epoch, **kwargs)

            # 执行一个 epoch 的训练
            epoch_result = self.train_epoch(epoch, **kwargs)

            # Epoch 结束钩子
            epoch_result['epoch'] = epoch
            epoch_result['time'] = time.time() - epoch_start_time
            self.on_epoch_end(epoch, epoch_result, **kwargs)

            history.append(epoch_result)

        # 5. 训练后钩子
        train_result = self.on_train_end(history, **kwargs)

        return train_result

    def train_epoch(self, epoch: int, **kwargs) -> Dict[str, Any]:
        """
        训练一个 epoch（子类可重写）

        Args:
            epoch: 当前 epoch 编号
            **kwargs: 额外参数

        Returns:
            Epoch 结果字典

        Note:
            默认实现调用所有 Worker 的 train_epoch() 方法并返回结果
            子类可以重写此方法实现自定义训练逻辑
        """
        # 默认：并行调用所有 Worker 的 train_epoch
        results = miniray.get([
            w.train_epoch.remote(epoch) for w in self.workers
        ])
        return {'worker_results': results}

    # ============================================================
    # 钩子方法（子类可选实现）
    # ============================================================

    def on_train_start(self, **kwargs):
        """训练开始前调用（子类可重写）"""
        print("[BaseTrainer] 训练开始...")

    def on_train_end(self, history: List[Dict], **kwargs) -> Dict[str, Any]:
        """
        训练结束后调用（子类可重写）

        Args:
            history: 所有 epoch 的结果列表

        Returns:
            最终训练结果
        """
        print("[BaseTrainer] 训练完成!")
        return {
            'history': history,
            'workers': self.workers,
            'num_epochs': len(history),
        }

    def on_epoch_start(self, epoch: int, **kwargs):
        """每个 epoch 开始前调用（子类可重写）"""
        print(f"\n[BaseTrainer] Epoch {epoch + 1} 开始...")

    def on_epoch_end(self, epoch: int, result: Dict, **kwargs):
        """
        每个 epoch 结束后调用（子类可重写）

        Args:
            epoch: Epoch 编号
            result: Epoch 结果
        """
        elapsed = result.get('time', 0)
        print(f"[BaseTrainer] Epoch {epoch + 1} 完成 (耗时: {elapsed:.2f}s)")

    # ============================================================
    # 辅助方法
    # ============================================================

    def _create_workers(self, **kwargs) -> List:
        """创建所有 Workers"""
        workers = []
        for i in range(self.num_workers):
            worker = self.create_worker(i, **kwargs)
            workers.append(worker)
        return workers

    def shutdown(self):
        """关闭 Mini-Ray"""
        if self._miniray_initialized:
            print("[BaseTrainer] 关闭 Mini-Ray...")
            miniray.shutdown()
            self._miniray_initialized = False

    def __enter__(self):
        """支持 with 语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 语句，自动关闭"""
        self.shutdown()

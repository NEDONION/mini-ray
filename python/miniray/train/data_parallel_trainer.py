"""
Data Parallel Trainer - 数据并行训练器

封装「多 Worker + 周期性参数平均」的数据并行训练模式
"""

from typing import List, Dict, Any, Optional, Callable
import numpy as np

import miniray
from miniray.ps import create_parameter_server
from miniray.train.base_trainer import BaseTrainer


class DataParallelTrainer(BaseTrainer):
    """
    数据并行训练器

    特点：
    1. 数据自动分片到各个 Worker
    2. 周期性参数同步（使用 ParameterServer）
    3. 结果自动聚合
    4. 支持自定义聚合策略

    使用场景：
    - 数据并行训练（PyTorch DDP、Horovod 风格）
    - 定期同步模型参数
    - 支持任意模型（GAN、ResNet、BERT 等）

    Worker 接口要求：
        - train_epoch(epoch) -> Dict: 训练一个 epoch，返回指标
        - get_weights() -> List[Tensor]: 获取模型参数
        - set_weights(weights) -> None: 设置模型参数
        - load_data_shard(shard_id, num_shards, **kwargs) -> None: 加载数据分片（可选）
    """

    def __init__(
        self,
        num_workers: int = 4,
        sync_interval: int = 1,
        sync_strategy: str = 'average',
        auto_init: bool = True,
        **strategy_kwargs
    ):
        """
        Args:
            num_workers: Worker 数量
            sync_interval: 参数同步间隔（每 N 个 epoch 同步一次）
            sync_strategy: 参数聚合策略 ('average', 'weighted', 'momentum')
            auto_init: 是否自动初始化 Mini-Ray
            **strategy_kwargs: 策略特定参数
        """
        super().__init__(num_workers=num_workers, auto_init=auto_init)

        self.sync_interval = sync_interval
        self.sync_strategy = sync_strategy
        self.strategy_kwargs = strategy_kwargs

        self.param_server = None

        print(f"[DataParallelTrainer] 配置:")
        print(f"  Workers: {num_workers}")
        print(f"  Sync Interval: {sync_interval} epochs")
        print(f"  Sync Strategy: {sync_strategy}")

    # ============================================================
    # 训练流程重写
    # ============================================================

    def on_train_start(self, **kwargs):
        """训练开始：创建 ParameterServer 和数据分片"""
        print("[DataParallelTrainer] 创建 ParameterServer...")
        self.param_server = create_parameter_server(
            self.sync_strategy,
            **self.strategy_kwargs
        )

        # 数据分片（如果 Worker 支持）
        print("[DataParallelTrainer] 加载数据分片...")
        self._load_data_shards(**kwargs)

    def train_epoch(self, epoch: int, **kwargs) -> Dict[str, Any]:
        """
        训练一个 epoch，并在需要时同步参数

        Args:
            epoch: 当前 epoch 编号

        Returns:
            Epoch 结果，包括聚合后的指标
        """
        # 1. 并行训练
        worker_results = miniray.get([
            w.train_epoch.remote(epoch) for w in self.workers
        ])

        # 2. 聚合结果
        aggregated = self._aggregate_results(worker_results)

        # 3. 参数同步
        if (epoch + 1) % self.sync_interval == 0:
            print(f"  🔄 同步参数 (epoch {epoch + 1})...")
            self.param_server.sync_from_workers.remote(self.workers)

            # 获取同步统计
            stats = miniray.get(self.param_server.get_stats.remote())
            aggregated['sync_version'] = stats['version']
            aggregated['synced'] = True
        else:
            aggregated['synced'] = False

        aggregated['worker_results'] = worker_results
        return aggregated

    def on_epoch_end(self, epoch: int, result: Dict, **kwargs):
        """每个 epoch 结束：打印聚合后的指标"""
        elapsed = result.get('time', 0)
        synced = "✅ 已同步" if result.get('synced', False) else ""

        print(f"[DataParallelTrainer] Epoch {epoch + 1} 完成 (耗时: {elapsed:.2f}s) {synced}")

        # 打印聚合指标
        for key, value in result.items():
            if key not in ['worker_results', 'epoch', 'time', 'synced', 'sync_version']:
                if isinstance(value, (int, float)):
                    print(f"  {key}: {value:.4f}")

    # ============================================================
    # 数据分片
    # ============================================================

    def _load_data_shards(self, **kwargs):
        """
        加载数据分片（如果 Worker 支持 load_data_shard 方法）

        Args:
            **kwargs: 传递给 load_data_shard 的参数（如 batch_size, dataset_path 等）
        """
        # 检查 Worker 是否有 load_data_shard 方法
        # 通过尝试调用来判断（如果不支持会报错，但我们捕获它）
        try:
            miniray.get([
                w.load_data_shard.remote(i, self.num_workers, **kwargs)
                for i, w in enumerate(self.workers)
            ])
            print(f"  ✅ 数据已分片到 {self.num_workers} 个 Workers")
        except Exception as e:
            # Worker 不支持 load_data_shard，跳过
            print(f"  ℹ️  Workers 不支持自动数据分片（这是正常的）")

    # ============================================================
    # 结果聚合
    # ============================================================

    def _aggregate_results(
        self,
        worker_results: List[Dict],
        aggregation_fn: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        聚合所有 Worker 的训练结果

        Args:
            worker_results: 所有 Worker 的结果列表
            aggregation_fn: 自定义聚合函数（可选）

        Returns:
            聚合后的结果字典

        Note:
            默认对数值类型字段取平均值
        """
        if aggregation_fn:
            return aggregation_fn(worker_results)

        # 默认聚合策略：对数值字段取平均
        aggregated = {}

        if not worker_results:
            return aggregated

        # 获取所有字段
        keys = set()
        for result in worker_results:
            if isinstance(result, dict):
                keys.update(result.keys())

        # 对每个字段聚合
        for key in keys:
            values = []
            for result in worker_results:
                if isinstance(result, dict) and key in result:
                    values.append(result[key])

            if not values:
                continue

            # 数值类型：取平均
            if isinstance(values[0], (int, float)):
                aggregated[key] = float(np.mean(values))
            # 其他类型：取第一个
            else:
                aggregated[key] = values[0]

        return aggregated

    # ============================================================
    # 辅助方法
    # ============================================================

    def set_worker_weight(self, worker_id: int, weight: float):
        """
        设置 Worker 权重（用于加权平均策略）

        Args:
            worker_id: Worker ID
            weight: 权重值（如样本数量）
        """
        if self.param_server:
            miniray.get(self.param_server.set_worker_weight.remote(worker_id, weight))

    def get_sync_stats(self) -> Dict:
        """获取参数同步统计信息"""
        if self.param_server:
            return miniray.get(self.param_server.get_stats.remote())
        return {}

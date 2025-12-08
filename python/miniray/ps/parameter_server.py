"""
轻量级参数服务器（Parameter Server Actor）

提供分布式训练中的参数管理和同步功能
"""

import torch
from typing import List, Optional, Dict

import miniray
from miniray.ps.strategies import get_strategy, SyncStrategy


@miniray.remote
class ParameterServer:
    """
    轻量级参数服务器

    职责：
    1. 存储全局参数
    2. 接收 Worker 权重并聚合
    3. 向 Worker 下发最新权重

    使用场景：
    - 数据并行训练
    - 周期性参数同步
    - 支持多种聚合策略
    """

    def __init__(self, strategy: str = 'average', **strategy_kwargs):
        """
        Args:
            strategy: 聚合策略名称 ('average', 'weighted', 'momentum')
            **strategy_kwargs: 策略特定参数
        """
        self.strategy: SyncStrategy = get_strategy(strategy, **strategy_kwargs)
        self.global_weights: Optional[List[torch.Tensor]] = None
        self.version = 0
        self.num_syncs = 0

        print(f"[ParameterServer] 初始化 - 策略: {strategy}")

    # ============================================================
    # 核心接口
    # ============================================================

    def pull_weights(self) -> Optional[List[torch.Tensor]]:
        """
        拉取全局参数（供 Worker 调用）

        Returns:
            全局参数列表，如果尚未初始化则返回 None
        """
        return self.global_weights

    def push_weights(self, worker_id: int, weights: List[torch.Tensor]):
        """
        单个 Worker 推送权重（异步更新场景）

        Args:
            worker_id: Worker ID
            weights: Worker 的参数列表

        Note:
            当前实现为同步策略，此方法暂不使用
            保留接口供未来异步训练扩展
        """
        # TODO: 实现异步参数更新
        pass

    def sync_from_workers(self, worker_refs: List) -> List[torch.Tensor]:
        """
        从 Workers 同步参数（主要接口）

        Args:
            worker_refs: Worker Actor 引用列表

        Returns:
            聚合后的全局参数

        Workflow:
            1. 收集所有 Worker 的权重
            2. 使用策略聚合
            3. 更新全局权重
            4. 下发给所有 Worker
        """
        # 1. 收集权重
        weight_lists = miniray.get([
            w.get_weights.remote() for w in worker_refs
        ])

        # 2. 聚合
        self.global_weights = self.strategy.aggregate(weight_lists)
        self.version += 1
        self.num_syncs += 1

        # 3. 下发
        miniray.get([
            w.set_weights.remote(self.global_weights) for w in worker_refs
        ])

        return self.global_weights

    # ============================================================
    # 辅助接口
    # ============================================================

    def get_version(self) -> int:
        """获取参数版本号"""
        return self.version

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'version': self.version,
            'num_syncs': self.num_syncs,
            'strategy': self.strategy.__class__.__name__,
            'initialized': self.global_weights is not None,
        }

    def set_worker_weight(self, worker_id: int, weight: float):
        """
        设置 Worker 权重（仅用于 WeightedAverageStrategy）

        Args:
            worker_id: Worker ID
            weight: 权重值（如样本数量）
        """
        if hasattr(self.strategy, 'set_worker_weight'):
            self.strategy.set_worker_weight(worker_id, weight)
        else:
            print(f"[ParameterServer] 当前策略不支持设置 Worker 权重")


# ============================================================
# 便捷函数
# ============================================================

def create_parameter_server(strategy: str = 'average', **kwargs):
    """
    创建 ParameterServer Actor（便捷函数）

    Args:
        strategy: 聚合策略
        **kwargs: 策略参数

    Returns:
        ParameterServer Actor 引用

    Examples:
        >>> ps = create_parameter_server('average')
        >>> ps = create_parameter_server('momentum', momentum=0.95)
        >>> ps = create_parameter_server('weighted')
    """
    return ParameterServer.remote(strategy, **kwargs)

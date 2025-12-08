"""
参数同步策略

提供多种参数聚合方法，用于分布式训练中的参数同步
"""

import torch
from typing import List, Optional


class SyncStrategy:
    """参数同步策略基类"""

    def aggregate(self, weight_lists: List[List[torch.Tensor]]) -> List[torch.Tensor]:
        """
        聚合多个 Worker 的权重

        Args:
            weight_lists: [[worker0_param0, worker0_param1, ...],
                          [worker1_param0, worker1_param1, ...], ...]

        Returns:
            聚合后的权重列表
        """
        raise NotImplementedError


class AverageStrategy(SyncStrategy):
    """简单平均策略（最常用）"""

    def aggregate(self, weight_lists: List[List[torch.Tensor]]) -> List[torch.Tensor]:
        num_workers = len(weight_lists)
        num_params = len(weight_lists[0])

        aggregated = []
        for p_idx in range(num_params):
            tensors = [weight_lists[w][p_idx] for w in range(num_workers)]

            # 只对浮点类型参数求平均
            if torch.is_floating_point(tensors[0]):
                avg_tensor = torch.stack(tensors).mean(dim=0)
            else:
                # int/bool 类型不平均，直接用第一个
                avg_tensor = tensors[0]

            aggregated.append(avg_tensor)

        return aggregated


class WeightedAverageStrategy(SyncStrategy):
    """加权平均策略（按样本数量加权）"""

    def __init__(self):
        self.worker_weights = {}  # {worker_id: weight}

    def set_worker_weight(self, worker_id: int, weight: float):
        """设置 Worker 的权重（如样本数量）"""
        self.worker_weights[worker_id] = weight

    def aggregate(self, weight_lists: List[List[torch.Tensor]]) -> List[torch.Tensor]:
        num_workers = len(weight_lists)
        num_params = len(weight_lists[0])

        # 如果没有设置权重，退化为简单平均
        if not self.worker_weights:
            weights = [1.0 / num_workers] * num_workers
        else:
            total = sum(self.worker_weights.values())
            weights = [self.worker_weights.get(i, 1.0) / total for i in range(num_workers)]

        aggregated = []
        for p_idx in range(num_params):
            tensors = [weight_lists[w][p_idx] for w in range(num_workers)]

            if torch.is_floating_point(tensors[0]):
                # 加权平均
                weighted_sum = sum(t * w for t, w in zip(tensors, weights))
                aggregated.append(weighted_sum)
            else:
                aggregated.append(tensors[0])

        return aggregated


class MomentumStrategy(SyncStrategy):
    """动量策略（指数移动平均）"""

    def __init__(self, momentum: float = 0.9):
        self.momentum = momentum
        self.global_weights: Optional[List[torch.Tensor]] = None

    def aggregate(self, weight_lists: List[List[torch.Tensor]]) -> List[torch.Tensor]:
        # 先计算当前批次的平均
        avg_strategy = AverageStrategy()
        current_avg = avg_strategy.aggregate(weight_lists)

        # 如果是第一次，直接使用平均值
        if self.global_weights is None:
            self.global_weights = current_avg
            return current_avg

        # 应用动量
        aggregated = []
        for glob, curr in zip(self.global_weights, current_avg):
            if torch.is_floating_point(glob):
                new_param = self.momentum * glob + (1 - self.momentum) * curr
            else:
                new_param = curr
            aggregated.append(new_param)

        self.global_weights = aggregated
        return aggregated


# 策略工厂
STRATEGIES = {
    'average': AverageStrategy,
    'weighted': WeightedAverageStrategy,
    'momentum': MomentumStrategy,
}


def get_strategy(name: str, **kwargs) -> SyncStrategy:
    """
    获取同步策略

    Args:
        name: 策略名称 ('average', 'weighted', 'momentum')
        **kwargs: 策略特定参数

    Examples:
        >>> strategy = get_strategy('average')
        >>> strategy = get_strategy('momentum', momentum=0.95)
    """
    if name not in STRATEGIES:
        raise ValueError(f"未知策略: {name}. 可选: {list(STRATEGIES.keys())}")

    return STRATEGIES[name](**kwargs)

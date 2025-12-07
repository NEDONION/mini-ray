"""
搜索算法 - 生成超参数配置

支持：
- GridSearch: 网格搜索（穷举所有组合）
- RandomSearch: 随机搜索
"""
import itertools
import random
from typing import Any, Dict, List, Iterator
from abc import ABC, abstractmethod


class SearchSpace:
    """搜索空间定义基类"""
    pass


class GridSearch(SearchSpace):
    """
    网格搜索 - 穷举所有参数组合

    Example:
        >>> grid_search([0.001, 0.01, 0.1])
    """
    def __init__(self, values: List[Any]):
        self.values = values

    def __repr__(self):
        return f"GridSearch({self.values})"


class RandomSearch(SearchSpace):
    """
    随机搜索 - 从分布中采样

    Example:
        >>> random_search([0.001, 0.01, 0.1], num_samples=5)
    """
    def __init__(self, values: List[Any], num_samples: int = 10):
        self.values = values
        self.num_samples = num_samples

    def __repr__(self):
        return f"RandomSearch({self.values}, n={self.num_samples})"


class Choice(SearchSpace):
    """
    从列表中选择（与 GridSearch 等价）

    Example:
        >>> choice(['adam', 'sgd', 'rmsprop'])
    """
    def __init__(self, values: List[Any]):
        self.values = values

    def __repr__(self):
        return f"Choice({self.values})"


class SearchAlgorithm(ABC):
    """搜索算法基类"""

    @abstractmethod
    def generate_configs(self, search_space: Dict[str, SearchSpace]) -> Iterator[Dict[str, Any]]:
        """生成参数配置"""
        pass


class GridSearchAlgorithm(SearchAlgorithm):
    """
    网格搜索算法

    生成所有参数组合的笛卡尔积
    """

    def generate_configs(self, search_space: Dict[str, SearchSpace]) -> Iterator[Dict[str, Any]]:
        """
        生成所有参数组合

        Args:
            search_space: 参数搜索空间
                例如: {'lr': GridSearch([0.01, 0.1]), 'batch_size': GridSearch([32, 64])}

        Yields:
            参数配置字典
                例如: {'lr': 0.01, 'batch_size': 32}
        """
        # 提取参数名和值列表
        param_names = []
        param_values = []

        for name, space in search_space.items():
            param_names.append(name)

            if isinstance(space, (GridSearch, Choice)):
                param_values.append(space.values)
            elif isinstance(space, RandomSearch):
                # 对于 RandomSearch，在网格搜索中使用所有值
                param_values.append(space.values)
            else:
                # 普通值（不是搜索空间）
                param_values.append([space])

        # 生成笛卡尔积
        for combination in itertools.product(*param_values):
            config = dict(zip(param_names, combination))
            yield config


class RandomSearchAlgorithm(SearchAlgorithm):
    """
    随机搜索算法

    从搜索空间中随机采样配置
    """

    def __init__(self, num_samples: int = 10, seed: int = None):
        """
        Args:
            num_samples: 采样数量
            seed: 随机种子
        """
        self.num_samples = num_samples
        self.seed = seed

        if seed is not None:
            random.seed(seed)

    def generate_configs(self, search_space: Dict[str, SearchSpace]) -> Iterator[Dict[str, Any]]:
        """
        随机生成配置

        Args:
            search_space: 参数搜索空间

        Yields:
            参数配置字典
        """
        param_names = list(search_space.keys())
        param_spaces = list(search_space.values())

        for _ in range(self.num_samples):
            config = {}

            for name, space in zip(param_names, param_spaces):
                if isinstance(space, (GridSearch, Choice, RandomSearch)):
                    # 从值列表中随机选择
                    config[name] = random.choice(space.values)
                else:
                    # 普通值
                    config[name] = space

            yield config


# 便捷函数
def grid_search(values: List[Any]) -> GridSearch:
    """创建网格搜索空间"""
    return GridSearch(values)


def random_search(values: List[Any], num_samples: int = 10) -> RandomSearch:
    """创建随机搜索空间"""
    return RandomSearch(values, num_samples)


def choice(values: List[Any]) -> Choice:
    """从列表中选择"""
    return Choice(values)

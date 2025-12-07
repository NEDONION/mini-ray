"""
Mini-Ray Tune - 超参数调优框架

提供简单易用的超参数搜索 API，支持网格搜索和随机搜索。

Example:
    >>> from miniray import tune
    >>>
    >>> def train_fn(config):
    ...     model = Model(lr=config['lr'], batch_size=config['batch_size'])
    ...     accuracy = model.train()
    ...     return {'accuracy': accuracy}
    ...
    >>> analysis = tune.run(
    ...     train_fn,
    ...     config={
    ...         'lr': tune.grid_search([0.001, 0.01, 0.1]),
    ...         'batch_size': tune.grid_search([32, 64, 128]),
    ...     },
    ...     metric='accuracy',
    ...     mode='max'
    ... )
    >>>
    >>> print(f"Best config: {analysis.best_config}")
    >>> print(f"Best accuracy: {analysis.best_result['accuracy']}")
"""

from .tune import run, TuneController
from .search import grid_search, random_search, choice
from .search import GridSearch, RandomSearch, Choice
from .search import GridSearchAlgorithm, RandomSearchAlgorithm
from .trial import Trial
from .analysis import Analysis

__all__ = [
    # 主要 API
    'run',
    'grid_search',
    'random_search',
    'choice',

    # 高级 API
    'TuneController',
    'Trial',
    'Analysis',

    # 搜索空间类
    'GridSearch',
    'RandomSearch',
    'Choice',

    # 搜索算法类
    'GridSearchAlgorithm',
    'RandomSearchAlgorithm',
]

__version__ = '0.1.0'

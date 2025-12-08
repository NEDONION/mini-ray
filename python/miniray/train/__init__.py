"""
Mini-Ray Train - 轻量级分布式训练框架

提供通用的训练抽象，避免重复编写训练循环代码
"""

from miniray.train.base_trainer import BaseTrainer
from miniray.train.data_parallel_trainer import DataParallelTrainer

__all__ = [
    'BaseTrainer',
    'DataParallelTrainer',
]

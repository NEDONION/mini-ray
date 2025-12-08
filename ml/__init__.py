"""
Mini-Ray ML Module

机器学习模块，包括 GAN 生成式模型（单机 + 分布式）

## 快速开始

### 训练

单机训练:
    python -m ml.gan.train --mode single --epochs 10

分布式训练 (4 Workers):
    python -m ml.gan.train --mode distributed --workers 4 --epochs 10 --sync-interval 5

### 生成

单机生成:
    python -m ml.gan.generate --model ./models/gan/generator.pth --num-images 10

分布式生成 (4 Workers):
    python -m ml.gan.generate --model ./models/gan/generator.pth --num-images 100 --distributed --workers 4

详细文档: help(ml.gan)
"""

# 确保 miniray 在路径中
import sys
import os
_current_dir = os.path.dirname(os.path.abspath(__file__))
_miniray_path = os.path.join(_current_dir, '..', 'python')
if _miniray_path not in sys.path:
    sys.path.insert(0, _miniray_path)

from ml.gan import (
    Generator,
    Discriminator,
    ImageGenerator,
    ImageGeneratorWorker,
    GANWorker,
    GANTrainer,
)

__all__ = [
    # GAN 模型
    'Generator',
    'Discriminator',

    # 单机训练和生成
    'ImageGenerator',

    # 分布式训练
    'GANWorker',
    'GANTrainer',

    # 分布式生成
    'ImageGeneratorWorker',
]

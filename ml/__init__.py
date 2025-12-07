"""
Mini-Ray ML Module (External)

机器学习相关功能，包括：
- GAN 生成式模型（单机 + 分布式）
- 训练和推理（单机 + 分布式）

使用方法:
    # 单机训练
    python -m ml.train --mode single --epochs 10

    # 分布式训练（4 个 Worker）
    python -m ml.train --mode distributed --workers 4 --epochs 10

    # 单机生成图片
    python -m ml.generate --model ./models/gan/generator.pth --num-images 10

    # 分布式生成图片（4 个 Worker）
    python -m ml.generate --model ./models/gan/generator.pth --num-images 100 --distributed --workers 4
"""
# 确保 miniray 在路径中
import sys
import os
_current_dir = os.path.dirname(os.path.abspath(__file__))
_miniray_path = os.path.join(_current_dir, '..', 'python')
if _miniray_path not in sys.path:
    sys.path.insert(0, _miniray_path)

from ml.gan_cifar10 import Generator, Discriminator, GANTrainer, ImageGenerator
from ml.distributed_gan import (
    DistributedGANWorker,
    DistributedGANTrainer,
    DistributedImageGenerator,
    DistributedImageGeneratorCoordinator
)
from ml.train import train_single, train_distributed
from ml.generate import generate_images, generate_images_distributed

__all__ = [
    # 模型
    'Generator',
    'Discriminator',

    # 单机训练和生成
    'GANTrainer',
    'ImageGenerator',

    # 分布式训练
    'DistributedGANWorker',
    'DistributedGANTrainer',

    # 分布式生成
    'DistributedImageGenerator',
    'DistributedImageGeneratorCoordinator',

    # 便捷函数
    'train_single',
    'train_distributed',
    'generate_images',
    'generate_images_distributed'
]

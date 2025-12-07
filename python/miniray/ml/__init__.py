"""
Mini-Ray ML Module

机器学习相关功能，包括：
- GAN 生成式模型（单机 + 分布式）
- 训练和推理（单机 + 分布式）

使用方法:
    # 单机训练
    python -m miniray.ml.train --mode single --epochs 10

    # 分布式训练（4 个 Worker）
    python -m miniray.ml.train --mode distributed --workers 4 --epochs 10

    # 单机生成图片
    python -m miniray.ml.generate --model ./models/gan/generator.pth --num-images 10

    # 分布式生成图片（4 个 Worker）
    python -m miniray.ml.generate --model ./models/gan/generator.pth --num-images 100 --distributed --workers 4
"""
from .gan_cifar10 import Generator, Discriminator, GANTrainer, ImageGenerator
from .distributed_gan import (
    DistributedGANWorker,
    DistributedGANTrainer,
    DistributedImageGenerator,
    DistributedImageGeneratorCoordinator
)
from .train import train_single, train_distributed
from .generate import generate_images, generate_images_distributed

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

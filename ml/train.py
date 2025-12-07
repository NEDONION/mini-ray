#!/usr/bin/env python3
"""
GAN 训练模块 - 支持单机和分布式训练
"""
import sys
import os

from ml.utils.data_utils import ensure_cifar10_downloaded

# 添加 python 路径以导入 miniray
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

import time
import argparse
from ml.gan_cifar10 import GANTrainer
from ml.distributed_gan import DistributedGANTrainer


def train_single(epochs=10, batch_size=128, latent_dim=100, lr=0.0002, save_dir='./models/gan'):
    """
    单机训练

    Args:
        epochs: 训练轮数
        batch_size: 批次大小
        latent_dim: 隐变量维度
        lr: 学习率
        save_dir: 模型保存目录

    Returns:
        训练历史
    """
    from miniray.dashboard import get_collector

    data_root = ensure_cifar10_downloaded(
        global_root="/data",
        project_root="./data"
    )

    print("\n" + "="*70)
    print("  单机 GAN 训练")
    print("="*70)
    print(f"\n配置:")
    print(f"  Epochs: {epochs}")
    print(f"  Batch Size: {batch_size}")
    print(f"  Latent Dim: {latent_dim}")
    print(f"  Learning Rate: {lr}")
    print()

    collector = get_collector()
    job_id = f"gan-single-{int(time.time())}"

    trainer = GANTrainer(latent_dim=latent_dim, lr=lr)

    history = trainer.train(
        epochs=epochs,
        batch_size=batch_size,
        job_id=job_id,
        collector=collector
    )

    trainer.save_models(save_dir)

    print(f"\n✅ 模型已保存到: {save_dir}")
    return history


def train_distributed(epochs=10, batch_size=128, num_workers=4, sync_interval=5,
                      latent_dim=100, lr=0.0002):
    """
    分布式训练

    Args:
        epochs: 训练轮数
        batch_size: 批次大小
        num_workers: Worker 数量
        sync_interval: 参数同步间隔
        latent_dim: 隐变量维度
        lr: 学习率

    Returns:
        训练历史, workers
    """
    from miniray.dashboard import get_collector

    data_root = ensure_cifar10_downloaded(
        global_root="/data",
        project_root="./data"
    )

    print("\n" + "="*70)
    print("  分布式 GAN 训练")
    print("="*70)
    print(f"\n配置:")
    print(f"  Epochs: {epochs}")
    print(f"  Batch Size: {batch_size}")
    print(f"  Workers: {num_workers}")
    print(f"  Sync Interval: {sync_interval} epochs")
    print(f"  Latent Dim: {latent_dim}")
    print(f"  Learning Rate: {lr}")
    print()

    collector = get_collector()
    job_id = f"gan-dist-{int(time.time())}"

    trainer = DistributedGANTrainer(
        num_workers=num_workers,
        latent_dim=latent_dim,
        lr=lr
    )

    history, workers = trainer.train(
        epochs=epochs,
        batch_size=batch_size,
        sync_interval=sync_interval,
        job_id=job_id,
        collector=collector
    )

    print(f"\n✅ 所有 Worker 模型已保存到: ./models/distributed_gan/")
    return history, workers


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='GAN Training for CIFAR-10')
    parser.add_argument('--mode', type=str, default='single', choices=['single', 'distributed'],
                        help='训练模式：single（单机）或 distributed（分布式）')
    parser.add_argument('--epochs', type=int, default=10, help='训练轮数')
    parser.add_argument('--batch-size', type=int, default=128, help='批次大小')
    parser.add_argument('--workers', type=int, default=4, help='Worker 数量（分布式模式）')
    parser.add_argument('--sync-interval', type=int, default=5, help='参数同步间隔（分布式模式）')
    parser.add_argument('--latent-dim', type=int, default=100, help='隐变量维度')
    parser.add_argument('--lr', type=float, default=0.0002, help='学习率')
    parser.add_argument('--save-dir', type=str, default='./models/gan', help='模型保存目录')

    args = parser.parse_args()

    if args.mode == 'single':
        train_single(
            epochs=args.epochs,
            batch_size=args.batch_size,
            latent_dim=args.latent_dim,
            lr=args.lr,
            save_dir=args.save_dir
        )
    else:
        train_distributed(
            epochs=args.epochs,
            batch_size=args.batch_size,
            num_workers=args.workers,
            sync_interval=args.sync_interval,
            latent_dim=args.latent_dim,
            lr=args.lr
        )


if __name__ == '__main__':
    main()

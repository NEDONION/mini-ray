#!/usr/bin/env python3
"""
GAN 训练入口 - 支持单机和分布式训练

使用方法:
    # 单机训练
    python -m ml.gan.train --mode single --epochs 10

    # 分布式训练
    python -m ml.gan.train --mode distributed --workers 4 --epochs 10
"""

import argparse
import sys
import os

# 添加 python 路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_python_path = os.path.join(_current_dir, '..', '..', 'python')
if _python_path not in sys.path:
    sys.path.insert(0, _python_path)


def train_single(args):
    """单机训练"""
    from ml.gan.models import GANTrainer
    from miniray import track_training_job

    print("\n" + "=" * 60)
    print("单机 GAN 训练")
    print("=" * 60)

    # 使用 Dashboard 跟踪注解
    @track_training_job(name=f"Single GAN Training - {args.job_id}",
                        description=f"单机 GAN 训练任务 - {args.job_id}")
    def run_training():
        trainer = GANTrainer(
            latent_dim=args.latent_dim,
            lr=args.lr,
            device=args.device
        )

        history = trainer.train(
            epochs=args.epochs,
            batch_size=args.batch_size,
            job_id=args.job_id
        )

        # 保存模型
        if args.save_dir:
            trainer.save_models(args.save_dir)

        print("\n" + "=" * 60)
        print("单机训练完成！")
        print(f"最终 G_loss: {history['g_loss'][-1]:.4f}")
        print(f"最终 D_loss: {history['d_loss'][-1]:.4f}")
        print("=" * 60)

        return history

    history = run_training()
    return history


def train_distributed(args):
    """分布式训练"""
    import miniray
    from ml.gan.distributed_trainer import GANTrainer
    from miniray import track_training_job

    print("\n" + "=" * 60)
    print("分布式 GAN 训练")
    print("=" * 60)

    # 使用 Dashboard 跟踪注解
    @track_training_job(name=f"Distributed GAN Training - {args.job_id}",
                        description=f"分布式 GAN 训练任务 - {args.job_id}, Workers: {args.workers}")
    def run_distributed_training():
        # 初始化 miniray
        miniray.init(num_workers=args.workers)

        try:
            trainer = GANTrainer(
                num_workers=args.workers,
                latent_dim=args.latent_dim,
                lr=args.lr,
                sync_interval=args.sync_interval,
                sync_strategy=args.sync_strategy
            )

            result = trainer.train(
                epochs=args.epochs,
                batch_size=args.batch_size
            )

            # 保存模型
            if args.save_dir:
                print(f"\n保存模型到 {args.save_dir}...")
                save_futures = [
                    w.save_models.remote(f"{args.save_dir}/worker_{i}")
                    for i, w in enumerate(trainer.workers)
                ]
                results = miniray.get(save_futures)
                for msg in results:
                    print(msg)

            print("\n" + "=" * 60)
            print("分布式训练完成！")
            print(f"总 epochs: {result['num_epochs']}")
            print("=" * 60)

            return result

        finally:
            trainer.shutdown()
            miniray.shutdown()

    result = run_distributed_training()
    return result


def main():
    parser = argparse.ArgumentParser(description='GAN 训练 - 单机/分布式')

    # 基础参数
    parser.add_argument('--mode', type=str, default='single',
                        choices=['single', 'distributed'],
                        help='训练模式: single 或 distributed')
    parser.add_argument('--epochs', type=int, default=10,
                        help='训练轮数 (默认: 10)')
    parser.add_argument('--batch-size', type=int, default=128,
                        help='批次大小 (默认: 128)')
    parser.add_argument('--latent-dim', type=int, default=100,
                        help='隐变量维度 (默认: 100)')
    parser.add_argument('--lr', type=float, default=0.0002,
                        help='学习率 (默认: 0.0002)')
    parser.add_argument('--device', type=str, default=None,
                        help='训练设备 (cpu/cuda, 默认自动检测)')
    parser.add_argument('--save-dir', type=str, default='./models/gan',
                        help='模型保存目录 (默认: ./models/gan)')
    parser.add_argument('--job-id', type=str, default='gan-train',
                        help='任务 ID (用于 Dashboard)')

    # 分布式参数
    parser.add_argument('--workers', type=int, default=4,
                        help='Worker 数量 (分布式模式, 默认: 4)')
    parser.add_argument('--sync-interval', type=int, default=5,
                        help='参数同步间隔 (分布式模式, 默认: 5)')
    parser.add_argument('--sync-strategy', type=str, default='average',
                        choices=['average', 'momentum', 'weighted'],
                        help='参数同步策略 (默认: average)')

    args = parser.parse_args()

    # 根据模式选择训练函数
    if args.mode == 'single':
        train_single(args)
    else:
        train_distributed(args)


if __name__ == '__main__':
    main()

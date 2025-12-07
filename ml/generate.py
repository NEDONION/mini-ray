#!/usr/bin/env python3
"""
GAN 图片生成模块 - 支持单机和分布式生成
"""
import sys
import os
# 添加 python 路径以导入 miniray
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

import argparse
import matplotlib.pyplot as plt
from ml.gan_cifar10 import ImageGenerator
from ml.distributed_gan import DistributedImageGeneratorCoordinator


def display_images(images, rows=2, cols=5, save_path=None):
    """
    显示生成的图片

    Args:
        images: 图片数组 (N, H, W, C)
        rows: 行数
        cols: 列数
        save_path: 保存路径（可选）
    """
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2, rows * 2))
    fig.suptitle('GAN Generated CIFAR-10 Images', fontsize=16)

    for i, ax in enumerate(axes.flat):
        if i < len(images):
            ax.imshow(images[i])
            ax.axis('off')
            ax.set_title(f'#{i+1}', fontsize=10)
        else:
            ax.axis('off')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"📊 预览图已保存: {save_path}")

    plt.show()


def generate_images(model_path, num_images=10, output_dir='./generated_images',
                   latent_dim=100, seed=None, show=True):
    """
    生成图片

    Args:
        model_path: 模型路径
        num_images: 生成数量
        output_dir: 输出目录
        latent_dim: 隐变量维度
        seed: 随机种子
        show: 是否显示图片

    Returns:
        生成的图片数组
    """
    print("\n" + "="*70)
    print("  GAN 图片生成")
    print("="*70)

    # 检查模型
    if not os.path.exists(model_path):
        print(f"\n❌ 模型文件不存在: {model_path}")
        print("\n请先训练模型:")
        print("  python -m miniray.ml.train --mode single --epochs 10")
        return None

    print(f"\n✅ 模型: {model_path}")
    print(f"📊 生成数量: {num_images}")
    if seed:
        print(f"🎲 随机种子: {seed}")

    # 创建生成器
    generator = ImageGenerator(latent_dim=latent_dim)
    generator.load_model(model_path)

    # 生成图片
    print(f"\n🎨 生成中...")
    images = generator.generate(num_images=num_images, seed=seed)

    # 保存
    generator.save_images(images, save_dir=output_dir)
    print(f"✅ 图片已保存到: {output_dir}")

    # 显示
    if show:
        print("\n📊 显示生成的图片...")
        rows = (num_images + 4) // 5
        cols = min(5, num_images)
        display_images(images, rows=rows, cols=cols,
                      save_path=f'{output_dir}/preview.png')

    print("\n✅ 完成！")
    return images


def generate_images_distributed(model_path, num_images=100, output_dir='./generated_images',
                                latent_dim=100, num_workers=4, seed=42):
    """
    分布式生成图片

    Args:
        model_path: 模型路径
        num_images: 生成数量
        output_dir: 输出目录
        latent_dim: 隐变量维度
        num_workers: Worker 数量
        seed: 随机种子

    Returns:
        生成的图片数组
    """
    print("\n" + "="*70)
    print("  分布式 GAN 图片生成")
    print("="*70)

    # 检查模型
    if not os.path.exists(model_path):
        print(f"\n❌ 模型文件不存在: {model_path}")
        print("\n请先训练模型:")
        print("  python -m miniray.ml.train --mode single --epochs 10")
        return None

    print(f"\n✅ 模型: {model_path}")
    print(f"📊 生成数量: {num_images}")
    print(f"👥 Workers: {num_workers}")
    if seed:
        print(f"🎲 随机种子: {seed}")

    # 创建分布式生成器
    coordinator = DistributedImageGeneratorCoordinator(
        num_workers=num_workers,
        latent_dim=latent_dim
    )

    # 生成图片
    images = coordinator.generate(
        model_path=model_path,
        num_images=num_images,
        save_dir=output_dir,
        seed=seed
    )

    print("\n✅ 完成！")
    return images


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='Generate images using trained GAN')
    parser.add_argument('--model', type=str, default='./models/gan/generator.pth',
                        help='生成器模型路径')
    parser.add_argument('--num-images', type=int, default=10, help='生成图片数量')
    parser.add_argument('--output', type=str, default='./generated_images',
                        help='输出目录')
    parser.add_argument('--latent-dim', type=int, default=100, help='隐变量维度')
    parser.add_argument('--seed', type=int, default=None, help='随机种子')
    parser.add_argument('--no-show', action='store_true', help='不显示图片')
    parser.add_argument('--distributed', action='store_true', help='使用分布式生成')
    parser.add_argument('--workers', type=int, default=4, help='Worker 数量（分布式模式）')

    args = parser.parse_args()

    if args.distributed:
        # 分布式生成
        generate_images_distributed(
            model_path=args.model,
            num_images=args.num_images,
            output_dir=args.output,
            latent_dim=args.latent_dim,
            num_workers=args.workers,
            seed=args.seed if args.seed else 42
        )
    else:
        # 单机生成
        generate_images(
            model_path=args.model,
            num_images=args.num_images,
            output_dir=args.output,
            latent_dim=args.latent_dim,
            seed=args.seed,
            show=not args.no_show
        )


if __name__ == '__main__':
    main()

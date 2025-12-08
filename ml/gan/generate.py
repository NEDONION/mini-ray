#!/usr/bin/env python3
"""
GAN 图片生成入口 - 支持单机和分布式生成

使用方法:
    # 单机生成
    python -m ml.gan.generate --model ./models/gan/generator.pth --num-images 10

    # 分布式生成
    python -m ml.gan.generate --model ./models/gan/generator.pth --num-images 100 --distributed --workers 4
"""

import argparse
import sys
import os
import time

# 添加 python 路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_python_path = os.path.join(_current_dir, '..', '..', 'python')
if _python_path not in sys.path:
    sys.path.insert(0, _python_path)


def generate_single(args):
    """单机生成"""
    from ml.gan.models import ImageGenerator

    print("\n" + "=" * 60)
    print("单机图片生成")
    print("=" * 60)

    generator = ImageGenerator(
        latent_dim=args.latent_dim,
        device=args.device
    )

    # 加载模型
    generator.load_model(args.model)

    # 生成图片
    print(f"\n生成 {args.num_images} 张图片...")
    start_time = time.time()

    images = generator.generate(
        num_images=args.num_images,
        seed=args.seed
    )

    elapsed = time.time() - start_time

    # 保存图片
    generator.save_images(images, args.output)

    print("\n" + "=" * 60)
    print("单机生成完成！")
    print(f"生成图片数: {len(images)}")
    print(f"用时: {elapsed:.2f}s")
    print(f"速度: {len(images)/elapsed:.2f} 张/秒")
    print(f"保存目录: {args.output}")
    print("=" * 60)


def generate_distributed(args):
    """分布式生成"""
    import miniray
    from ml.gan.models import ImageGeneratorWorker

    if ImageGeneratorWorker is None:
        print("[错误] miniray 不可用，无法使用分布式生成")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("分布式图片生成")
    print("=" * 60)

    # 初始化 miniray
    miniray.init(num_workers=args.workers)

    try:
        # 创建 Workers
        print(f"\n创建 {args.workers} 个生成 Workers...")
        workers = [
            ImageGeneratorWorker.remote(i, latent_dim=args.latent_dim, device=args.device)
            for i in range(args.workers)
        ]

        # 加载模型
        print(f"加载模型: {args.model}")
        load_futures = [w.load_model.remote(args.model) for w in workers]
        miniray.get(load_futures)

        # 分配任务：每个 Worker 生成 num_images // workers 张图片
        images_per_worker = args.num_images // args.workers
        remaining = args.num_images % args.workers

        print(f"\n生成 {args.num_images} 张图片 (每个 Worker ~{images_per_worker} 张)...")
        start_time = time.time()

        # 分配任务
        generate_futures = []
        for i, w in enumerate(workers):
            # 最后一个 Worker 处理余数
            count = images_per_worker + (remaining if i == args.workers - 1 else 0)
            seed = args.seed + i if args.seed is not None else None

            future = w.generate.remote(count, seed)
            generate_futures.append(future)

        # 等待生成完成
        all_images = miniray.get(generate_futures)

        elapsed = time.time() - start_time

        # 保存图片（每个 Worker 保存自己的图片）
        print(f"\n保存图片到 {args.output}...")
        save_futures = []
        start_idx = 0
        for i, w in enumerate(workers):
            future = w.save_images.remote(all_images[i], args.output, start_idx)
            save_futures.append(future)
            start_idx += len(all_images[i])

        # 等待保存完成
        miniray.get(save_futures)

        total_images = sum(len(imgs) for imgs in all_images)

        print("\n" + "=" * 60)
        print("分布式生成完成！")
        print(f"生成图片数: {total_images}")
        print(f"用时: {elapsed:.2f}s")
        print(f"速度: {total_images/elapsed:.2f} 张/秒")
        print(f"加速比: ~{args.workers}x (理论)")
        print(f"保存目录: {args.output}")
        print("=" * 60)

    finally:
        miniray.shutdown()


def main():
    parser = argparse.ArgumentParser(description='GAN 图片生成 - 单机/分布式')

    # 基础参数
    parser.add_argument('--model', type=str, required=True,
                        help='生成器模型路径 (必需)')
    parser.add_argument('--num-images', type=int, default=10,
                        help='生成图片数量 (默认: 10)')
    parser.add_argument('--output', type=str, default='./generated',
                        help='输出目录 (默认: ./generated)')
    parser.add_argument('--latent-dim', type=int, default=100,
                        help='隐变量维度 (默认: 100)')
    parser.add_argument('--seed', type=int, default=None,
                        help='随机种子 (可选)')
    parser.add_argument('--device', type=str, default=None,
                        help='设备 (cpu/cuda, 默认自动检测)')

    # 分布式参数
    parser.add_argument('--distributed', action='store_true',
                        help='使用分布式生成')
    parser.add_argument('--workers', type=int, default=4,
                        help='Worker 数量 (分布式模式, 默认: 4)')

    args = parser.parse_args()

    # 检查模型文件是否存在
    if not os.path.exists(args.model):
        print(f"[错误] 模型文件不存在: {args.model}")
        sys.exit(1)

    # 根据模式选择生成函数
    if args.distributed:
        generate_distributed(args)
    else:
        generate_single(args)


if __name__ == '__main__':
    main()

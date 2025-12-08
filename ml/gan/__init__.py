"""
GAN 模块 - CIFAR-10 图片生成

支持单机和分布式训练、生成

## 命令行使用

### 训练

单机训练:
    python -m ml.gan.train --mode single --epochs 10

分布式训练:
    python -m ml.gan.train --mode distributed --workers 4 --epochs 10 --sync-interval 5

参数:
    --mode              训练模式 (single 或 distributed)
    --epochs            训练轮数
    --batch-size        批次大小 (默认: 128)
    --workers           Worker 数量 (分布式, 默认: 4)
    --sync-interval     参数同步间隔 (分布式, 默认: 5)
    --sync-strategy     同步策略 (average/momentum/weighted)
    --save-dir          模型保存目录 (默认: ./models/gan)

### 生成

单机生成:
    python -m ml.gan.generate --model ./models/gan/generator.pth --num-images 10

分布式生成:
    python -m ml.gan.generate --model ./models/gan/generator.pth --num-images 100 --distributed --workers 4

参数:
    --model             生成器模型路径 (必需)
    --num-images        生成图片数量 (默认: 10)
    --output            输出目录 (默认: ./generated)
    --distributed       启用分布式生成
    --workers           Worker 数量 (分布式, 默认: 4)
    --seed              随机种子 (可选)

## Python API

单机训练:
    from ml.gan import GANTrainer
    trainer = GANTrainer(latent_dim=100, lr=0.0002)
    trainer.train(epochs=10, batch_size=128)

分布式训练:
    import miniray
    from ml.gan import GANTrainer
    miniray.init(num_workers=4)
    trainer = GANTrainer(num_workers=4, sync_interval=5)
    trainer.train(epochs=10, batch_size=128)
    trainer.shutdown()

单机生成:
    from ml.gan import ImageGenerator
    gen = ImageGenerator()
    gen.load_model('./models/gan/generator.pth')
    images = gen.generate(num_images=10)

分布式生成:
    import miniray
    from ml.gan import ImageGeneratorWorker
    miniray.init(num_workers=4)
    workers = [ImageGeneratorWorker.remote(i) for i in range(4)]
    [w.load_model.remote('./models/gan/generator.pth') for w in workers]
    images = miniray.get([w.generate.remote(25) for w in workers])
"""

from ml.gan.models import Generator, Discriminator, ImageGenerator, ImageGeneratorWorker
from ml.gan.distributed_trainer import GANWorker, GANTrainer

__all__ = [
    # 模型
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

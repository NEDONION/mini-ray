"""
分布式 GAN 训练 - 使用 Mini-Ray

使用 Mini-Ray 的 @remote 装饰器实现分布式训练
支持多种分布式策略：
1. 数据并行 - 多个 Worker 并行训练，定期同步参数
2. 分布式数据加载 - 并行加载和预处理数据
"""
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Subset
import numpy as np
import time
import os
import sys

# 导入 miniray - 添加 python 路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_python_path = os.path.join(_current_dir, '..', 'python')
if _python_path not in sys.path:
    sys.path.insert(0, _python_path)
import miniray

from ml.gan_cifar10 import Generator, Discriminator


# ============================================================
# 分布式训练 Worker
# ============================================================

@miniray.remote
class DistributedGANWorker:
    """
    分布式 GAN 训练 Worker

    每个 Worker 在自己的数据分片上训练 GAN
    """

    def __init__(self, worker_id, latent_dim=100, lr=0.0002, device=None):
        self.worker_id = worker_id
        self.latent_dim = latent_dim
        self.lr = lr
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        print(f"[Worker {worker_id}] 初始化分布式 GAN Worker - 设备: {self.device}")

        # 创建网络
        self.generator = Generator(latent_dim).to(self.device)
        self.discriminator = Discriminator().to(self.device)

        # 优化器
        self.optimizer_G = optim.Adam(self.generator.parameters(), lr=lr, betas=(0.5, 0.999))
        self.optimizer_D = optim.Adam(self.discriminator.parameters(), lr=lr, betas=(0.5, 0.999))

        # 损失函数
        self.criterion = nn.BCELoss()

    def load_data_shard(self, shard_id, num_shards, batch_size=128):
        """
        加载数据分片

        Args:
            shard_id: 分片 ID
            num_shards: 总分片数
            batch_size: 批次大小
        """
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        ])

        # 加载完整数据集
        full_dataset = torchvision.datasets.CIFAR10(
            root='./data',
            train=True,
            download=False,
            transform=transform
        )

        # 计算此 Worker 负责的数据范围
        total_size = len(full_dataset)
        shard_size = total_size // num_shards
        start_idx = shard_id * shard_size
        end_idx = start_idx + shard_size if shard_id < num_shards - 1 else total_size

        # 创建数据分片
        indices = list(range(start_idx, end_idx))
        shard_dataset = Subset(full_dataset, indices)

        self.dataloader = DataLoader(
            shard_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0  # 避免在 Worker 中再创建子进程
        )

        print(f"[Worker {self.worker_id}] 数据分片 {shard_id}/{num_shards}: {len(shard_dataset)} 张图片")

    def train_epoch(self, epoch):
        """
        训练一个 epoch

        Args:
            epoch: 当前 epoch

        Returns:
            训练指标字典
        """
        epoch_g_loss = 0.0
        epoch_d_loss = 0.0
        num_batches = 0

        for i, (real_images, _) in enumerate(self.dataloader):
            batch_size = real_images.size(0)
            real_images = real_images.to(self.device)

            # 标签
            real_labels = torch.ones(batch_size, 1).to(self.device)
            fake_labels = torch.zeros(batch_size, 1).to(self.device)

            # ========================================
            # 训练 Discriminator
            # ========================================
            self.optimizer_D.zero_grad()

            # 真实图片
            real_output = self.discriminator(real_images)
            d_loss_real = self.criterion(real_output, real_labels)

            # 假图片
            z = torch.randn(batch_size, self.latent_dim).to(self.device)
            fake_images = self.generator(z)
            fake_output = self.discriminator(fake_images.detach())
            d_loss_fake = self.criterion(fake_output, fake_labels)

            d_loss = d_loss_real + d_loss_fake
            d_loss.backward()
            self.optimizer_D.step()

            # ========================================
            # 训练 Generator
            # ========================================
            self.optimizer_G.zero_grad()

            z = torch.randn(batch_size, self.latent_dim).to(self.device)
            fake_images = self.generator(z)
            fake_output = self.discriminator(fake_images)

            g_loss = self.criterion(fake_output, real_labels)
            g_loss.backward()
            self.optimizer_G.step()

            epoch_g_loss += g_loss.item()
            epoch_d_loss += d_loss.item()
            num_batches += 1

        # 返回平均损失
        return {
            'worker_id': self.worker_id,
            'epoch': epoch,
            'g_loss': epoch_g_loss / num_batches,
            'd_loss': epoch_d_loss / num_batches,
            'num_batches': num_batches
        }

    def get_model_state(self):
        """获取模型参数"""
        return {
            'generator': self.generator.state_dict(),
            'discriminator': self.discriminator.state_dict()
        }

    def set_model_state(self, state_dict):
        """设置模型参数"""
        self.generator.load_state_dict(state_dict['generator'])
        self.discriminator.load_state_dict(state_dict['discriminator'])

    def save_models(self, save_dir):
        """保存模型"""
        os.makedirs(save_dir, exist_ok=True)
        torch.save(self.generator.state_dict(), f'{save_dir}/generator_worker{self.worker_id}.pth')
        torch.save(self.discriminator.state_dict(), f'{save_dir}/discriminator_worker{self.worker_id}.pth')
        return f"Worker {self.worker_id} 模型已保存"


# ============================================================
# 分布式训练协调器
# ============================================================

class DistributedGANTrainer:
    """
    分布式 GAN 训练协调器

    使用数据并行策略：
    1. 启动多个 Worker，每个处理一部分数据
    2. 并行训练
    3. 定期同步参数（平均聚合）

    使用方法:
        trainer = DistributedGANTrainer(num_workers=4)
        trainer.train(epochs=50, batch_size=128, job_id='dist-gan-001')
    """

    def __init__(self, num_workers=4, latent_dim=100, lr=0.0002):
        """
        初始化分布式训练器

        Args:
            num_workers: Worker 数量
            latent_dim: 隐变量维度
            lr: 学习率
        """
        self.num_workers = num_workers
        self.latent_dim = latent_dim
        self.lr = lr

        print(f"\n[DistributedGANTrainer] 初始化")
        print(f"  Workers: {num_workers}")
        print(f"  Latent Dim: {latent_dim}")
        print(f"  Learning Rate: {lr}")

    def train(self, epochs=50, batch_size=128, sync_interval=5, job_id=None, collector=None):
        """
        开始分布式训练

        Args:
            epochs: 训练轮数
            batch_size: 批次大小
            sync_interval: 参数同步间隔（每 N 个 epoch）
            job_id: 任务 ID
            collector: Dashboard 收集器

        Returns:
            训练历史
        """
        print(f"\n{'='*70}")
        print(f"  开始分布式 GAN 训练")
        print(f"{'='*70}")
        print(f"  Epochs: {epochs}")
        print(f"  Batch Size: {batch_size}")
        print(f"  Sync Interval: {sync_interval} epochs")
        print(f"  Workers: {self.num_workers}")
        print()

        # 初始化 Mini-Ray
        if not hasattr(miniray, '_initialized') or not miniray._initialized:
            miniray.init(num_workers=self.num_workers)
            print(f"✅ Mini-Ray 已初始化 ({self.num_workers} workers)")

        # Dashboard 初始化
        if collector and job_id:
            collector.record_training_job(
                job_id=job_id,
                name=f"Distributed GAN Training ({self.num_workers} Workers)",
                status='Running',
                progress=0.0,
                config={
                    'model': 'Distributed GAN',
                    'dataset': 'CIFAR-10',
                    'num_workers': self.num_workers,
                    'epochs': epochs,
                    'batch_size': batch_size,
                    'sync_interval': sync_interval
                },
                metrics={}
            )
            collector.add_training_log(job_id, f"[INFO] 分布式训练启动 - {self.num_workers} Workers")

        # 创建分布式 Workers
        print(f"🚀 创建 {self.num_workers} 个训练 Workers...")
        workers = []
        for i in range(self.num_workers):
            worker = DistributedGANWorker.remote(
                worker_id=i,
                latent_dim=self.latent_dim,
                lr=self.lr
                # device 参数已省略，会自动检测：优先 GPU，无 GPU 则用 CPU
            )
            workers.append(worker)

        # 加载数据分片
        print(f"📦 分发数据到各个 Worker...")
        load_refs = []
        for i, worker in enumerate(workers):
            ref = worker.load_data_shard.remote(
                shard_id=i,
                num_shards=self.num_workers,
                batch_size=batch_size
            )
            load_refs.append(ref)

        # 等待数据加载完成（数据加载可能需要时间下载 CIFAR-10）
        miniray.get(load_refs, timeout_s=300.0)  # 5 分钟超时
        print("✅ 所有 Worker 数据加载完成\n")

        if collector and job_id:
            collector.add_training_log(job_id, f"[INFO] 数据分片完成，每个 Worker 处理 1/{self.num_workers} 的数据")

        history = {
            'epochs': [],
            'avg_g_loss': [],
            'avg_d_loss': []
        }

        # 训练循环
        for epoch in range(epochs):
            epoch_start = time.time()

            # 并行训练一个 epoch
            print(f"[Epoch {epoch+1}/{epochs}] 所有 Workers 并行训练...")
            train_refs = []
            for worker in workers:
                ref = worker.train_epoch.remote(epoch)
                train_refs.append(ref)

            # 收集结果（GAN 训练一个 epoch 可能需要几分钟）
            results = miniray.get(train_refs, timeout_s=600.0)  # 10 分钟超时

            # 聚合结果
            avg_g_loss = np.mean([r['g_loss'] for r in results])
            avg_d_loss = np.mean([r['d_loss'] for r in results])
            epoch_time = time.time() - epoch_start
            progress = ((epoch + 1) / epochs) * 100

            history['epochs'].append(epoch + 1)
            history['avg_g_loss'].append(avg_g_loss)
            history['avg_d_loss'].append(avg_d_loss)

            print(f"[Epoch {epoch+1}/{epochs}] 完成:")
            print(f"  Avg G_loss: {avg_g_loss:.4f} (across {self.num_workers} workers)")
            print(f"  Avg D_loss: {avg_d_loss:.4f}")
            print(f"  Time: {epoch_time:.2f}s")
            print(f"  Progress: {progress:.1f}%\n")

            # 更新 Dashboard
            if collector and job_id:
                collector.record_training_job(
                    job_id=job_id,
                    name=f"Distributed GAN Training ({self.num_workers} Workers)",
                    status='Running',
                    progress=progress,
                    config={
                        'model': 'Distributed GAN',
                        'num_workers': self.num_workers,
                        'current_epoch': epoch + 1,
                        'total_epochs': epochs
                    },
                    metrics={
                        'g_loss': float(avg_g_loss),
                        'd_loss': float(avg_d_loss),
                        'epoch': epoch + 1
                    }
                )
                collector.add_training_log(
                    job_id,
                    f"[INFO] Epoch {epoch+1}/{epochs} | Avg G_loss: {avg_g_loss:.4f} | Avg D_loss: {avg_d_loss:.4f} | {epoch_time:.1f}s"
                )

            # 参数同步（每 N 个 epoch）
            if (epoch + 1) % sync_interval == 0 and epoch < epochs - 1:
                print(f"🔄 同步模型参数...")

                # 获取所有 Worker 的参数
                state_refs = [worker.get_model_state.remote() for worker in workers]
                states = miniray.get(state_refs, timeout_s=60.0)

                # 平均聚合参数
                avg_state = self._average_model_states(states)

                # 广播到所有 Worker
                sync_refs = [worker.set_model_state.remote(avg_state) for worker in workers]
                miniray.get(sync_refs, timeout_s=60.0)

                print(f"✅ 参数同步完成\n")

                if collector and job_id:
                    collector.add_training_log(job_id, f"[INFO] 参数同步完成（Epoch {epoch+1}）")

        # 训练完成
        print(f"\n{'='*70}")
        print(f"  ✅ 分布式训练完成！")
        print(f"{'='*70}")

        if collector and job_id:
            collector.record_training_job(
                job_id=job_id,
                name=f"Distributed GAN Training ({self.num_workers} Workers)",
                status='Completed',
                progress=100.0,
                config={'model': 'Distributed GAN', 'num_workers': self.num_workers},
                metrics={
                    'final_g_loss': float(history['avg_g_loss'][-1]),
                    'final_d_loss': float(history['avg_d_loss'][-1])
                }
            )
            collector.add_training_log(job_id, f"[SUCCESS] 训练完成！")

        # 保存模型
        print("\n💾 保存所有 Worker 的模型...")
        save_refs = [worker.save_models.remote(f'./models/distributed_gan/worker_{i}')
                     for i, worker in enumerate(workers)]
        messages = miniray.get(save_refs, timeout_s=60.0)
        for msg in messages:
            print(f"  {msg}")

        return history, workers

    def _average_model_states(self, states):
        """
        聚合来自多个 Worker 的模型参数（参数平均）。

        处理规则：
        - 浮点张量（权重/偏置/BN running stats）：
            使用 stack + mean 做参数平均。
        - 整型/布尔张量（如 BatchNorm.num_batches_tracked）：
            无法平均，也没有平均意义，直接取第 0 个 Worker 的值。
        - 非 Tensor 类型：
            直接取第 0 个 Worker 的值。

        参数:
            states: List[Dict]
                每个 Worker 返回的 state_dict 列表。

        返回:
            avg_state: Dict
                聚合后的模型参数字典。
        """
        avg_state = {}

        for model_name in ['generator', 'discriminator']:
            avg_state[model_name] = {}
            param_names = states[0][model_name].keys()

            for param_name in param_names:
                params = [s[model_name][param_name] for s in states]
                first = params[0]

                # 非 tensor（比如 None、标量）直接拿第一个
                if not isinstance(first, torch.Tensor):
                    avg_state[model_name][param_name] = first
                    continue

                # 浮点 / 复数：做平均
                if torch.is_floating_point(first) or torch.is_complex(first):
                    stacked = torch.stack(params, dim=0)
                    avg_param = stacked.mean(dim=0)
                    avg_state[model_name][param_name] = avg_param
                else:
                    # 整型 / Bool：直接用第一个 worker 的值即可
                    # 典型如 BatchNorm.num_batches_tracked
                    avg_state[model_name][param_name] = first

        return avg_state


# ============================================================
# 分布式图片生成
# ============================================================

@miniray.remote
class DistributedImageGenerator:
    """
    分布式图片生成 Worker

    每个 Worker 并行生成一部分图片
    """

    def __init__(self, worker_id, latent_dim=100, device=None):
        self.worker_id = worker_id
        self.latent_dim = latent_dim
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.generator = None
        print(f"[Generator Worker {worker_id}] 初始化 - 设备: {self.device}")

    def load_model(self, model_path):
        """加载生成器模型"""
        self.generator = Generator(self.latent_dim).to(self.device)
        self.generator.load_state_dict(torch.load(model_path, map_location=self.device))
        self.generator.eval()
        return f"Worker {self.worker_id} 模型加载完成"

    def generate_batch(self, num_images, seed_offset=0):
        """
        生成一批图片

        Args:
            num_images: 生成数量
            seed_offset: 随机种子偏移（用于确保不同 Worker 生成不同图片）

        Returns:
            生成的图片数组 (N, H, W, C)
        """
        if self.generator is None:
            raise RuntimeError("模型未加载，请先调用 load_model()")

        # 设置随机种子
        if seed_offset is not None:
            torch.manual_seed(seed_offset + self.worker_id)
            np.random.seed(seed_offset + self.worker_id)

        with torch.no_grad():
            # 生成随机噪声
            z = torch.randn(num_images, self.latent_dim).to(self.device)

            # 生成图片
            fake_images = self.generator(z)

            # 转换到 numpy 格式: (N, C, H, W) -> (N, H, W, C)
            images = fake_images.cpu().numpy()
            images = np.transpose(images, (0, 2, 3, 1))

            # 反归一化: [-1, 1] -> [0, 1]
            images = (images + 1) / 2.0
            images = np.clip(images, 0, 1)

        return images


class DistributedImageGeneratorCoordinator:
    """
    分布式图片生成协调器

    使用多个 Worker 并行生成大量图片

    使用方法:
        coordinator = DistributedImageGeneratorCoordinator(num_workers=4)
        images = coordinator.generate(
            model_path='./models/gan/generator.pth',
            num_images=100,
            save_dir='./output'
        )
    """

    def __init__(self, num_workers=4, latent_dim=100):
        """
        初始化分布式生成协调器

        Args:
            num_workers: Worker 数量
            latent_dim: 隐变量维度
        """
        self.num_workers = num_workers
        self.latent_dim = latent_dim

        print(f"\n[DistributedImageGenerator] 初始化")
        print(f"  Workers: {num_workers}")
        print(f"  Latent Dim: {latent_dim}")

    def generate(self, model_path, num_images=100, save_dir='./generated_images', seed=42):
        """
        并行生成图片

        Args:
            model_path: 生成器模型路径
            num_images: 总共生成的图片数量
            save_dir: 保存目录
            seed: 随机种子

        Returns:
            所有生成的图片数组
        """
        print(f"\n{'='*70}")
        print(f"  分布式图片生成")
        print(f"{'='*70}")
        print(f"  Model: {model_path}")
        print(f"  Total Images: {num_images}")
        print(f"  Workers: {self.num_workers}")
        print(f"  Images per Worker: ~{num_images // self.num_workers}")
        print()

        # 检查模型文件
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        # 初始化 Mini-Ray
        if not hasattr(miniray, '_initialized') or not miniray._initialized:
            miniray.init(num_workers=self.num_workers)
            print(f"✅ Mini-Ray 已初始化 ({self.num_workers} workers)")

        # 创建分布式生成 Workers
        print(f"🚀 创建 {self.num_workers} 个生成 Workers...")
        workers = []
        for i in range(self.num_workers):
            worker = DistributedImageGenerator.remote(
                worker_id=i,
                latent_dim=self.latent_dim
                # device 参数已省略，会自动检测：优先 GPU，无 GPU 则用 CPU
            )
            workers.append(worker)

        # 加载模型到所有 Workers
        print(f"📦 加载模型到所有 Workers...")
        load_refs = [worker.load_model.remote(model_path) for worker in workers]
        messages = miniray.get(load_refs, timeout_s=60.0)
        for msg in messages:
            print(f"  {msg}")

        # 计算每个 Worker 生成的图片数量
        images_per_worker = num_images // self.num_workers
        remaining = num_images % self.num_workers

        # 并行生成图片
        print(f"\n🎨 开始并行生成 {num_images} 张图片...")
        gen_refs = []
        for i, worker in enumerate(workers):
            # 最后一个 Worker 处理余数
            worker_images = images_per_worker + (remaining if i == self.num_workers - 1 else 0)
            ref = worker.generate_batch.remote(
                num_images=worker_images,
                seed_offset=seed + i * 1000 if seed else None
            )
            gen_refs.append(ref)

        # 收集结果
        print(f"📥 等待所有 Workers 完成...")
        image_batches = miniray.get(gen_refs, timeout_s=300.0)

        # 合并所有图片
        all_images = np.concatenate(image_batches, axis=0)
        print(f"✅ 共生成 {len(all_images)} 张图片")

        # 保存图片
        print(f"\n💾 保存图片到 {save_dir}...")
        os.makedirs(save_dir, exist_ok=True)

        from PIL import Image
        for i, img in enumerate(all_images):
            # 转换为 PIL Image 并保存
            img_pil = Image.fromarray((img * 255).astype(np.uint8))
            img_pil.save(f'{save_dir}/generated_{i:04d}.png')

        print(f"✅ 所有图片已保存到 {save_dir}")
        print(f"\n{'='*70}")
        print(f"  ✅ 分布式生成完成！")
        print(f"{'='*70}\n")

        return all_images

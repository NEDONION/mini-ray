"""
分布式 GAN 训练器 - 使用 miniray.train 框架

展示如何使用 DataParallelTrainer 简化训练代码
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Subset

import numpy as np
import os
import sys

# 导入 miniray python 路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_python_path = os.path.join(_current_dir, '..', '..', 'python')
if _python_path not in sys.path:
    sys.path.insert(0, _python_path)

import miniray
from miniray.train import DataParallelTrainer
from ml.gan.models import Generator, Discriminator


# ============================================================
# GAN Worker
# ============================================================

@miniray.remote
class GANWorker:
    """GAN 训练 Worker"""

    def __init__(self, worker_id, latent_dim=100, lr=0.0002, device=None):
        self.worker_id = worker_id
        self.latent_dim = latent_dim
        self.lr = lr
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        print(f"[Worker {worker_id}] 初始化 - 设备: {self.device}")

        self.generator = Generator(latent_dim).to(self.device)
        self.discriminator = Discriminator().to(self.device)

        self.optimizer_G = optim.Adam(self.generator.parameters(), lr=lr, betas=(0.5, 0.999))
        self.optimizer_D = optim.Adam(self.discriminator.parameters(), lr=lr, betas=(0.5, 0.999))

        self.criterion = nn.BCELoss()
        self.dataloader = None

    def load_data_shard(self, shard_id, num_shards, batch_size=128):
        """加载数据分片"""
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,))
        ])

        dataset = torchvision.datasets.CIFAR10(
            root="./data",
            train=True,
            download=False,
            transform=transform
        )

        total_size = len(dataset)
        per_shard = total_size // num_shards

        start = shard_id * per_shard
        end = total_size if shard_id == num_shards - 1 else start + per_shard

        indices = list(range(start, end))
        shard = Subset(dataset, indices)

        self.dataloader = DataLoader(
            shard,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0
        )

        print(f"[Worker {self.worker_id}] 加载数据 {len(shard)} 张图像")

    def train_epoch(self, epoch):
        """训练一个 epoch"""
        g_total = 0
        d_total = 0
        batches = 0

        for real_images, _ in self.dataloader:
            real_images = real_images.to(self.device)
            bsz = real_images.size(0)

            real_labels = torch.ones(bsz, 1).to(self.device)
            fake_labels = torch.zeros(bsz, 1).to(self.device)

            # ========== Train D ==========
            self.optimizer_D.zero_grad()

            out_real = self.discriminator(real_images)
            loss_real = self.criterion(out_real, real_labels)

            z = torch.randn(bsz, self.latent_dim).to(self.device)
            fake = self.generator(z)
            out_fake = self.discriminator(fake.detach())
            loss_fake = self.criterion(out_fake, fake_labels)

            d_loss = loss_real + loss_fake
            d_loss.backward()
            self.optimizer_D.step()

            # ========== Train G ==========
            self.optimizer_G.zero_grad()

            z = torch.randn(bsz, self.latent_dim).to(self.device)
            fake = self.generator(z)
            out_fake = self.discriminator(fake)
            g_loss = self.criterion(out_fake, real_labels)

            g_loss.backward()
            self.optimizer_G.step()

            g_total += g_loss.item()
            d_total += d_loss.item()
            batches += 1

        return {
            "worker_id": self.worker_id,
            "epoch": epoch,
            "g_loss": g_total / batches,
            "d_loss": d_total / batches
        }

    def get_weights(self):
        """返回 generator 和 discriminator 的参数（线性化）"""
        weights = []

        for param in self.generator.state_dict().values():
            weights.append(param.detach().cpu())

        for param in self.discriminator.state_dict().values():
            weights.append(param.detach().cpu())

        return weights

    def set_weights(self, weights):
        """从线性化参数列表恢复模型参数"""
        idx = 0

        gen_sd = self.generator.state_dict()
        for key in gen_sd.keys():
            gen_sd[key] = weights[idx].to(self.device)
            idx += 1
        self.generator.load_state_dict(gen_sd)

        disc_sd = self.discriminator.state_dict()
        for key in disc_sd.keys():
            disc_sd[key] = weights[idx].to(self.device)
            idx += 1
        self.discriminator.load_state_dict(disc_sd)

    def save_models(self, save_dir):
        os.makedirs(save_dir, exist_ok=True)
        torch.save(self.generator.state_dict(), f"{save_dir}/generator_{self.worker_id}.pth")
        torch.save(self.discriminator.state_dict(), f"{save_dir}/discriminator_{self.worker_id}.pth")
        return f"[Worker {self.worker_id}] 模型已保存"


# ============================================================
# GAN Trainer - 使用 DataParallelTrainer（超简洁！）
# ============================================================

class GANTrainer(DataParallelTrainer):
    """
    GAN 分布式训练器

    相比原始实现（~250 行代码）：
    - 只需实现 create_worker() 和 on_epoch_end()
    - 数据分片、参数同步、训练循环全部自动处理
    - 代码量减少 90%+
    """

    def __init__(
        self,
        num_workers: int = 4,
        latent_dim: int = 100,
        lr: float = 0.0002,
        sync_interval: int = 5,
        sync_strategy: str = 'average'
    ):
        super().__init__(
            num_workers=num_workers,
            sync_interval=sync_interval,
            sync_strategy=sync_strategy
        )

        self.latent_dim = latent_dim
        self.lr = lr

    def create_worker(self, worker_id, **kwargs):
        """创建 GAN Worker"""
        return GANWorker.remote(worker_id, self.latent_dim, self.lr)

    def on_epoch_end(self, epoch: int, result: dict, **kwargs):
        """每个 epoch 结束：打印 GAN 专用指标"""
        # 调用父类方法打印基础信息
        super().on_epoch_end(epoch, result, **kwargs)

        # 打印 GAN 专用指标（已经被聚合）
        g_loss = result.get('g_loss', 0)
        d_loss = result.get('d_loss', 0)
        print(f"  G_loss: {g_loss:.4f}, D_loss: {d_loss:.4f}")


# ============================================================
# 使用示例
# ============================================================

def main():
    print("\n" + "=" * 60)
    print("GAN 训练示例 - 使用 miniray.train 框架")
    print("=" * 60)

    # 创建 Trainer（极简！）
    trainer = GANTrainer(
        num_workers=4,
        latent_dim=100,
        lr=0.0002,
        sync_interval=5,
        sync_strategy='average'  # 可选: 'momentum', 'weighted'
    )

    # 训练（一行搞定！）
    result = trainer.train(
        epochs=10,
        batch_size=128  # 传递给 load_data_shard
    )

    print("\n" + "=" * 60)
    print("训练完成!")
    print(f"总 epochs: {result['num_epochs']}")
    print("=" * 60)

    # 关闭
    trainer.shutdown()


if __name__ == "__main__":
    main()

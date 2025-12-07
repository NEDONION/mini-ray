"""
分布式 GAN 训练 - 使用 Mini-Ray

支持多种分布式策略：
1. 数据并行（多个 Worker 训练，周期性参数同步）
2. 分布式数据加载
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

# 导入 miniray python 路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_python_path = os.path.join(_current_dir, '..', 'python')
if _python_path not in sys.path:
    sys.path.insert(0, _python_path)

import miniray
from ml.gan_cifar10 import Generator, Discriminator


# ============================================================
# 分布式 Worker：训练 CIFAR-10 GAN
# ============================================================

@miniray.remote
class DistributedGANWorker:
    """每个 Worker 在自己的数据分片上训练 GAN"""

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

    # ============================
    # 参数同步接口（线性化参数列表）
    # ============================

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
# Trainer：分布式 GAN 调度器
# ============================================================

class DistributedGANTrainer:

    def __init__(self, num_workers=4, latent_dim=100, lr=0.0002):
        self.num_workers = num_workers
        self.latent_dim = latent_dim
        self.lr = lr

        print("\n[DistributedGANTrainer] 初始化")
        print(f" Workers: {num_workers}")
        print(f" Latent Dim: {latent_dim}")
        print(f" Learning Rate: {lr}")

    def train(self, epochs=50, batch_size=128, sync_interval=5):
        print("========== 启动 Mini-Ray ==========")
        miniray.init(num_workers=self.num_workers)

        print("========== 创建 Workers ==========")
        workers = [
            DistributedGANWorker.remote(i, self.latent_dim, self.lr)
            for i in range(self.num_workers)
        ]

        print("========== 加载数据 ==========")
        miniray.get([
            w.load_data_shard.remote(i, self.num_workers, batch_size)
            for i, w in enumerate(workers)
        ])

        history = []

        for epoch in range(epochs):
            print(f"\n===== Epoch {epoch+1}/{epochs} =====")

            # --------- 并行训练 ---------
            results = miniray.get([
                w.train_epoch.remote(epoch)
                for w in workers
            ])

            g_loss = np.mean([r["g_loss"] for r in results])
            d_loss = np.mean([r["d_loss"] for r in results])
            history.append((g_loss, d_loss))

            print(f"G_loss = {g_loss:.4f}, D_loss = {d_loss:.4f}")

            # --------- 参数同步 ---------
            if (epoch + 1) % sync_interval == 0:
                print("🔄 同步参数...")

                weight_lists = miniray.get([w.get_weights.remote() for w in workers])

                num_params = len(weight_lists[0])
                avg_weights = []

                for p in range(num_params):
                    tensors = [weight_lists[w][p] for w in range(self.num_workers)]
                    t0 = tensors[0]

                    if torch.is_floating_point(t0):
                        avg = torch.stack(tensors).mean(0)
                    else:
                        avg = t0  # int/bool 不能平均

                    avg_weights.append(avg)

                miniray.get([w.set_weights.remote(avg_weights) for w in workers])
                print("✅ 权重同步完成")

        return history, workers


# ============================================================
# 分布式图片生成 Worker
# ============================================================

@miniray.remote
class DistributedImageGenerator:

    def __init__(self, worker_id, latent_dim=100, device=None):
        self.worker_id = worker_id
        self.latent_dim = latent_dim
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        print(f"[Generator Worker {worker_id}] 初始化 - 设备: {self.device}")
        self.generator = None

    def load_model(self, model_path):
        self.generator = Generator(self.latent_dim).to(self.device)
        self.generator.load_state_dict(torch.load(model_path, map_location=self.device))
        self.generator.eval()
        return f"Worker {self.worker_id} 模型加载完成"

    def generate_batch(self, num_images, seed_offset=0):
        if self.generator is None:
            raise RuntimeError("请先调用 load_model()")

        torch.manual_seed(seed_offset + self.worker_id)
        np.random.seed(seed_offset + self.worker_id)

        with torch.no_grad():
            z = torch.randn(num_images, self.latent_dim).to(self.device)
            imgs = self.generator(z)

            imgs = imgs.cpu().numpy()
            imgs = np.transpose(imgs, (0, 2, 3, 1))  # CHW → HWC
            imgs = (imgs + 1) / 2.0
            imgs = np.clip(imgs, 0, 1)

        return imgs


# ============================================================
# 分布式图片生成协调器
# ============================================================

class DistributedImageGeneratorCoordinator:

    def __init__(self, num_workers=4, latent_dim=100):
        self.num_workers = num_workers
        self.latent_dim = latent_dim

    def generate(self, model_path, num_images=100, save_dir="./generated_images", seed=42):

        print("\n========== 分布式图片生成 ==========")

        if not os.path.exists(model_path):
            raise FileNotFoundError(model_path)

        miniray.init(num_workers=self.num_workers)

        workers = [
            DistributedImageGenerator.remote(i, self.latent_dim)
            for i in range(self.num_workers)
        ]

        miniray.get([w.load_model.remote(model_path) for w in workers])

        per_worker = num_images // self.num_workers
        remain = num_images % self.num_workers

        refs = []
        for i, w in enumerate(workers):
            n = per_worker + (remain if i == self.num_workers - 1 else 0)
            refs.append(w.generate_batch.remote(n, seed + i * 1000))

        batches = miniray.get(refs)
        all_imgs = np.concatenate(batches, axis=0)

        os.makedirs(save_dir, exist_ok=True)
        from PIL import Image

        for i, img in enumerate(all_imgs):
            Image.fromarray((img * 255).astype(np.uint8)).save(
                f"{save_dir}/generated_{i:04d}.png"
            )

        print(f"已生成 {len(all_imgs)} 张图片，保存于 {save_dir}")

        return all_imgs

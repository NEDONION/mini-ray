"""
分布式 GAN 训练（最终稳定版）
- 不再使用共享内存传模型参数（避免 data_region full）
- 参数同步基于 RPC（get_weights / set_weights）
- 参数顺序固定为 sorted(key)
- 支持浮点参数平均，整数/布尔参数直接取 worker0
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

# 添加 miniray python 路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_python_path = os.path.join(_current_dir, '..', 'python')
if _python_path not in sys.path:
    sys.path.insert(0, _python_path)

import miniray
from ml.gan_cifar10 import Generator, Discriminator


# ============================================================
# Worker：训练单个 shard 的 GAN
# ============================================================

@miniray.remote
class DistributedGANWorker:
    def __init__(self, worker_id, latent_dim=100, lr=0.0002, device=None):
        self.worker_id = worker_id
        self.latent_dim = latent_dim
        self.lr = lr
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        print(f"[Worker {worker_id}] 初始化 - 设备: {self.device}")

        self.generator = Generator(latent_dim).to(self.device)
        self.discriminator = Discriminator().to(self.device)

        self.optimizer_G = optim.Adam(self.generator.parameters(), lr=lr, betas=(0.5, 0.999))
        self.optimizer_D = optim.Adam(self.discriminator.parameters(), lr=lr, betas=(0.5, 0.999))

        self.criterion = nn.BCELoss()
        self.dataloader = None

    def load_data_shard(self, shard_id, num_shards, batch_size=128, dataset_root='./data'):
        """加载分片数据"""
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        ])

        full_dataset = torchvision.datasets.CIFAR10(
            root=dataset_root,
            train=True,
            download=False,
            transform=transform
        )

        total_size = len(full_dataset)
        per_shard = total_size // num_shards
        start = shard_id * per_shard
        end = (start + per_shard) if shard_id < num_shards - 1 else total_size

        subset = Subset(full_dataset, list(range(start, end)))

        self.dataloader = DataLoader(subset, batch_size=batch_size, shuffle=True, num_workers=0)

        print(f"[Worker {self.worker_id}] 数据加载完成，共 {len(subset)} 张图像")

    def train_epoch(self, epoch):
        """训练一个 epoch"""
        g_loss_total = 0
        d_loss_total = 0
        batches = 0

        for real_images, _ in self.dataloader:
            real_images = real_images.to(self.device)
            bsz = real_images.size(0)

            real_labels = torch.ones(bsz, 1).to(self.device)
            fake_labels = torch.zeros(bsz, 1).to(self.device)

            # ----------- train D ----------------
            self.optimizer_D.zero_grad()

            out_real = self.discriminator(real_images)
            loss_real = self.criterion(out_real, real_labels)

            z = torch.randn(bsz, self.latent_dim).to(self.device)
            fake_imgs = self.generator(z)
            out_fake = self.discriminator(fake_imgs.detach())
            loss_fake = self.criterion(out_fake, fake_labels)

            d_loss = loss_real + loss_fake
            d_loss.backward()
            self.optimizer_D.step()

            # ----------- train G ----------------
            self.optimizer_G.zero_grad()

            z = torch.randn(bsz, self.latent_dim).to(self.device)
            fake_imgs = self.generator(z)
            out_fake = self.discriminator(fake_imgs)
            g_loss = self.criterion(out_fake, real_labels)
            g_loss.backward()
            self.optimizer_G.step()

            g_loss_total += g_loss.item()
            d_loss_total += d_loss.item()
            batches += 1

        return {
            "worker_id": self.worker_id,
            "epoch": epoch,
            "g_loss": g_loss_total / batches,
            "d_loss": d_loss_total / batches,
        }

    # ======================================================
    # 参数同步接口（最终修正版）
    # ======================================================

    def get_weights(self):
        """按排序顺序返回模型参数（Tensor 列表）"""
        weights = []

        # generator
        gen_sd = self.generator.state_dict()
        for key in sorted(gen_sd.keys()):
            weights.append(gen_sd[key].detach().cpu())

        # discriminator
        disc_sd = self.discriminator.state_dict()
        for key in sorted(disc_sd.keys()):
            weights.append(disc_sd[key].detach().cpu())

        return weights

    def set_weights(self, weights):
        """按相同顺序恢复参数"""
        idx = 0

        gen_sd = self.generator.state_dict()
        for key in sorted(gen_sd.keys()):
            gen_sd[key] = weights[idx].to(self.device)
            idx += 1
        self.generator.load_state_dict(gen_sd)

        disc_sd = self.discriminator.state_dict()
        for key in sorted(disc_sd.keys()):
            disc_sd[key] = weights[idx].to(self.device)
            idx += 1
        self.discriminator.load_state_dict(disc_sd)

    def save_models(self, path):
        os.makedirs(path, exist_ok=True)
        torch.save(self.generator.state_dict(), f"{path}/generator_{self.worker_id}.pth")
        torch.save(self.discriminator.state_dict(), f"{path}/discriminator_{self.worker_id}.pth")
        return f"[Worker {self.worker_id}] 模型已保存"


# ============================================================
# Trainer：负责调度多个 Worker
# ============================================================

class DistributedGANTrainer:
    def __init__(self, num_workers=4, latent_dim=100, lr=0.0002):
        self.num_workers = num_workers
        self.latent_dim = latent_dim
        self.lr = lr

    def train(self, epochs=50, batch_size=128, sync_interval=20):
        print("========== 启动 Mini-Ray ==========")
        miniray.init(num_workers=self.num_workers)

        print("========== 启动 Workers ==========")
        workers = []
        for i in range(self.num_workers):
            w = DistributedGANWorker.remote(i, self.latent_dim, self.lr)
            workers.append(w)

        print("========== 加载分布式数据 ==========")
        refs = [w.load_data_shard.remote(i, self.num_workers, batch_size) for i, w in enumerate(workers)]
        miniray.get(refs)

        history = []

        # ===========================
        # 主训练循环
        # ===========================
        for epoch in range(epochs):
            print(f"\n===== Epoch {epoch+1}/{epochs} =====")

            # 1) 并行训练
            train_refs = [w.train_epoch.remote(epoch) for w in workers]
            results = miniray.get(train_refs)

            g_loss = np.mean([r["g_loss"] for r in results])
            d_loss = np.mean([r["d_loss"] for r in results])
            print(f"[Epoch {epoch+1}] G_loss={g_loss:.4f}  D_loss={d_loss:.4f}")

            history.append((g_loss, d_loss))

            # 2) 参数同步
            if (epoch + 1) % sync_interval == 0:
                print("🔄 同步参数中...")

                # RPC 获取所有 worker 权重
                w_lists = miniray.get([w.get_weights.remote() for w in workers])

                num_params = len(w_lists[0])
                avg_weights = []

                # 平均参数（处理 dtype）
                for p in range(num_params):
                    tensors = [w_lists[w][p] for w in range(self.num_workers)]
                    t0 = tensors[0]

                    if torch.is_floating_point(t0):
                        avg = torch.stack(tensors).mean(0)
                    else:
                        avg = t0  # int/bool 不能平均

                    avg_weights.append(avg)

                # 广播平均参数
                miniray.get([w.set_weights.remote(avg_weights) for w in workers])
                print("✅ 参数同步完成")

        print("\n===== 训练结束 =====")
        return history, workers

# ============================================================
# 分布式图片生成 Worker
# ============================================================

@miniray.remote
class DistributedImageGenerator:
    """
    负责加载 Generator 并生成图片
    """
    def __init__(self, worker_id, latent_dim=100, device=None):
        self.worker_id = worker_id
        self.latent_dim = latent_dim
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.generator = None
        print(f"[GenWorker {worker_id}] 初始化 - 设备: {self.device}")

    def load_model(self, model_path):
        """加载训练好的 Generator 模型"""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型不存在: {model_path}")

        self.generator = Generator(self.latent_dim).to(self.device)
        self.generator.load_state_dict(torch.load(model_path, map_location=self.device))
        self.generator.eval()
        return f"[GenWorker {self.worker_id}] 模型加载完成"

    def generate_images(self, num_images, seed=None):
        """生成批量图片并返回 numpy 数组"""
        if self.generator is None:
            raise RuntimeError("Generator 未加载，请先调用 load_model()")

        if seed is not None:
            torch.manual_seed(seed + self.worker_id)
            np.random.seed(seed + self.worker_id)

        with torch.no_grad():
            z = torch.randn(num_images, self.latent_dim).to(self.device)
            fake = self.generator(z)

            # (N, C, H, W) → (N, H, W, C)
            imgs = fake.cpu().numpy()
            imgs = np.transpose(imgs, (0, 2, 3, 1))

            # 反归一化 [-1,1] → [0,1]
            imgs = (imgs + 1) / 2.0
            imgs = np.clip(imgs, 0, 1)

            return imgs


# ============================================================
# 分布式图片生成协调器（可独立使用）
# ============================================================

class DistributedImageGeneratorCoordinator:
    """
    控制多个 Worker 并行生成大量图片
    """

    def __init__(self, num_workers=4, latent_dim=100):
        self.num_workers = num_workers
        self.latent_dim = latent_dim

    def generate(self, model_path, total_images=100, save_dir="./generated_images", seed=42):
        print("\n====================== 分布式图片生成 ======================")
        print(f"模型: {model_path}")
        print(f"总图片数: {total_images}")
        print(f"Workers: {self.num_workers}")

        # 初始化 Mini-Ray
        if not hasattr(miniray, "_initialized") or not miniray._initialized:
            miniray.init(num_workers=self.num_workers)
            print(f"Mini-Ray 已初始化 ({self.num_workers} workers)")

        # 启动 Workers
        workers = [
            DistributedImageGenerator.remote(i, self.latent_dim)
            for i in range(self.num_workers)
        ]

        # 加载模型
        print("📦 加载模型到 Workers ...")
        load_refs = [w.load_model.remote(model_path) for w in workers]
        msgs = miniray.get(load_refs)
        for msg in msgs:
            print(msg)

        # 每个 worker 的生成数量
        base = total_images // self.num_workers
        extra = total_images % self.num_workers

        gen_refs = []
        for i, w in enumerate(workers):
            n = base + (extra if i == self.num_workers - 1 else 0)
            ref = w.generate_images.remote(n, seed=seed)
            gen_refs.append(ref)

        print("🎨 正在生成图片 ...")
        batches = miniray.get(gen_refs)

        # 合并所有结果
        imgs = np.concatenate(batches, axis=0)
        print(f"生成完成: {imgs.shape[0]} 张")

        # 保存图片
        os.makedirs(save_dir, exist_ok=True)
        from PIL import Image

        for idx, img in enumerate(imgs):
            pil_img = Image.fromarray((img * 255).astype(np.uint8))
            pil_img.save(f"{save_dir}/generated_{idx:04d}.png")

        print(f"已保存到 {save_dir}")
        print("\n====================== 完成 ======================\n")

        return imgs

"""
CIFAR-10 GAN (Generative Adversarial Network)

生成式对抗网络用于生成 CIFAR-10 风格的图片
"""
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
import numpy as np
import time
import os


# ============================================================
# Generator 网络
# ============================================================

# CIFAR-10 DCGAN 风格 Generator
class Generator(nn.Module):
    def __init__(self, latent_dim=100, ngf=64):
        super().__init__()
        self.latent_dim = latent_dim
        self.main = nn.Sequential(
            # 输入 z: (N, latent_dim, 1, 1)
            nn.ConvTranspose2d(latent_dim, ngf*4, 4, 1, 0, bias=False),  # 4x4
            nn.BatchNorm2d(ngf*4),
            nn.ReLU(True),

            nn.ConvTranspose2d(ngf*4, ngf*2, 4, 2, 1, bias=False),       # 8x8
            nn.BatchNorm2d(ngf*2),
            nn.ReLU(True),

            nn.ConvTranspose2d(ngf*2, ngf, 4, 2, 1, bias=False),         # 16x16
            nn.BatchNorm2d(ngf),
            nn.ReLU(True),

            nn.ConvTranspose2d(ngf, 3, 4, 2, 1, bias=False),             # 32x32
            nn.Tanh()
        )

    def forward(self, z):
        # z: (N, latent_dim)
        z = z.view(-1, self.latent_dim, 1, 1)
        return self.main(z)


# CIFAR-10 DCGAN 风格 Discriminator
class Discriminator(nn.Module):
    def __init__(self, ndf=64):
        super().__init__()
        self.main = nn.Sequential(
            # 输入: (N,3,32,32)
            nn.Conv2d(3, ndf, 4, 2, 1, bias=False),      # 16x16
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(ndf, ndf*2, 4, 2, 1, bias=False),  # 8x8
            nn.BatchNorm2d(ndf*2),
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(ndf*2, ndf*4, 4, 2, 1, bias=False), # 4x4
            nn.BatchNorm2d(ndf*4),
            nn.LeakyReLU(0.2, inplace=True),

            nn.Conv2d(ndf*4, 1, 4, 1, 0, bias=False),    # 1x1
            nn.Sigmoid()
        )

    def forward(self, x):
        out = self.main(x)       # (N,1,1,1)
        return out.view(-1, 1)


# ============================================================
# GAN 训练器
# ============================================================

class GANTrainer:
    """
    GAN 训练器

    使用方法:
        trainer = GANTrainer(latent_dim=100, lr=0.0002)
        trainer.train(epochs=50, batch_size=128, job_id='gan-001')
    """

    def __init__(self, latent_dim=100, lr=0.0002, device=None):
        """
        初始化训练器

        Args:
            latent_dim: 隐变量维度
            lr: 学习率
            device: 训练设备 (cuda/cpu)
        """
        self.latent_dim = latent_dim
        self.lr = lr
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        print(f"[GANTrainer] 初始化完成 - 设备: {self.device}")

        # 创建网络
        self.generator = Generator(latent_dim).to(self.device)
        self.discriminator = Discriminator().to(self.device)

        # 优化器
        self.optimizer_G = optim.Adam(self.generator.parameters(), lr=lr, betas=(0.5, 0.999))
        self.optimizer_D = optim.Adam(self.discriminator.parameters(), lr=lr, betas=(0.5, 0.999))

        # 损失函数
        self.criterion = nn.BCELoss()

    def get_dataloader(self, batch_size=128, num_workers=2):
        """
        获取 CIFAR-10 数据加载器

        Args:
            batch_size: 批次大小
            num_workers: 数据加载线程数

        Returns:
            DataLoader
        """
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))  # 归一化到 [-1, 1]
        ])

        # 这里能不能指定路径加载。比如说从 data_utils.py 的返回值里知道data 路径
        dataset = torchvision.datasets.CIFAR10(
            root='./data',
            train=True,
            download=True,
            transform=transform
        )

        dataloader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=num_workers
        )

        return dataloader

    def train(self, epochs=50, batch_size=128, job_id=None, collector=None):
        """
        训练 GAN

        Args:
            epochs: 训练轮数
            batch_size: 批次大小
            job_id: 任务 ID（用于 Dashboard）
            collector: Dashboard 数据收集器

        Returns:
            训练历史
        """
        # 获取数据
        dataloader = self.get_dataloader(batch_size)
        total_steps = len(dataloader) * epochs

        print(f"\n[GANTrainer] 开始训练")
        print(f"  Epochs: {epochs}")
        print(f"  Batch Size: {batch_size}")
        print(f"  Total Steps: {total_steps}")
        print(f"  Device: {self.device}\n")

        # 初始化记录到 Dashboard
        if collector and job_id:
            collector.record_training_job(
                job_id=job_id,
                name="GAN CIFAR-10 Training",
                status='Running',
                progress=0.0,
                config={
                    'model': 'GAN',
                    'dataset': 'CIFAR-10',
                    'epochs': epochs,
                    'batch_size': batch_size,
                    'latent_dim': self.latent_dim,
                    'lr': self.lr
                },
                metrics={}
            )
            collector.add_training_log(job_id, "[INFO] GAN 训练开始")
            collector.add_training_log(job_id, f"[INFO] 设备: {self.device}")
            collector.add_training_log(job_id, f"[INFO] 数据集大小: {len(dataloader.dataset)} 张图片")

        history = {
            'g_loss': [],
            'd_loss': [],
            'epochs': []
        }

        step = 0
        for epoch in range(epochs):
            epoch_g_loss = 0.0
            epoch_d_loss = 0.0
            num_batches = 0

            for i, (real_images, _) in enumerate(dataloader):
                batch_size_actual = real_images.size(0)
                real_images = real_images.to(self.device)

                # 真实/假标签
                real_labels = torch.ones(batch_size_actual, 1).to(self.device)
                fake_labels = torch.zeros(batch_size_actual, 1).to(self.device)

                # ========================================
                # 训练 Discriminator
                # ========================================
                self.optimizer_D.zero_grad()

                # 真实图片
                real_output = self.discriminator(real_images)
                d_loss_real = self.criterion(real_output, real_labels)

                # 生成假图片
                z = torch.randn(batch_size_actual, self.latent_dim).to(self.device)
                fake_images = self.generator(z)
                fake_output = self.discriminator(fake_images.detach())
                d_loss_fake = self.criterion(fake_output, fake_labels)

                # 总判别器损失
                d_loss = d_loss_real + d_loss_fake
                d_loss.backward()
                self.optimizer_D.step()

                # ========================================
                # 训练 Generator
                # ========================================
                self.optimizer_G.zero_grad()

                z = torch.randn(batch_size_actual, self.latent_dim).to(self.device)
                fake_images = self.generator(z)
                fake_output = self.discriminator(fake_images)

                # 生成器希望判别器认为假图片是真的
                g_loss = self.criterion(fake_output, real_labels)
                g_loss.backward()
                self.optimizer_G.step()

                # 记录损失
                epoch_g_loss += g_loss.item()
                epoch_d_loss += d_loss.item()
                num_batches += 1
                step += 1

                # 每 50 步打印一次
                if (i + 1) % 50 == 0:
                    print(f"[Epoch {epoch+1}/{epochs}] [Batch {i+1}/{len(dataloader)}] "
                          f"D_loss: {d_loss.item():.4f} | G_loss: {g_loss.item():.4f}")

            # Epoch 结束
            avg_g_loss = epoch_g_loss / num_batches
            avg_d_loss = epoch_d_loss / num_batches
            progress = ((epoch + 1) / epochs) * 100

            history['g_loss'].append(avg_g_loss)
            history['d_loss'].append(avg_d_loss)
            history['epochs'].append(epoch + 1)

            print(f"\n[Epoch {epoch+1}/{epochs}] 完成:")
            print(f"  Avg G_loss: {avg_g_loss:.4f}")
            print(f"  Avg D_loss: {avg_d_loss:.4f}")
            print(f"  Progress: {progress:.1f}%\n")

            # 更新 Dashboard
            if collector and job_id:
                collector.record_training_job(
                    job_id=job_id,
                    name="GAN CIFAR-10 Training",
                    status='Running',
                    progress=progress,
                    config={
                        'model': 'GAN',
                        'dataset': 'CIFAR-10',
                        'epochs': epochs,
                        'batch_size': batch_size,
                        'latent_dim': self.latent_dim,
                        'lr': self.lr,
                        'current_epoch': epoch + 1
                    },
                    metrics={
                        'g_loss': float(avg_g_loss),
                        'd_loss': float(avg_d_loss),
                        'epoch': epoch + 1
                    }
                )
                collector.add_training_log(
                    job_id,
                    f"[INFO] Epoch {epoch+1}/{epochs} | G_loss: {avg_g_loss:.4f} | D_loss: {avg_d_loss:.4f}"
                )

        # 训练完成
        if collector and job_id:
            collector.record_training_job(
                job_id=job_id,
                name="GAN CIFAR-10 Training",
                status='Completed',
                progress=100.0,
                config={
                    'model': 'GAN',
                    'dataset': 'CIFAR-10',
                    'epochs': epochs,
                    'batch_size': batch_size
                },
                metrics={
                    'final_g_loss': float(history['g_loss'][-1]),
                    'final_d_loss': float(history['d_loss'][-1])
                }
            )
            collector.add_training_log(job_id, f"[SUCCESS] 训练完成！")
            collector.add_training_log(job_id, f"[SUCCESS] 最终 G_loss: {history['g_loss'][-1]:.4f}")
            collector.add_training_log(job_id, f"[SUCCESS] 最终 D_loss: {history['d_loss'][-1]:.4f}")

        print("\n[GANTrainer] 训练完成！")
        return history

    def save_models(self, save_dir='./models'):
        """保存模型"""
        os.makedirs(save_dir, exist_ok=True)
        torch.save(self.generator.state_dict(), f'{save_dir}/generator.pth')
        torch.save(self.discriminator.state_dict(), f'{save_dir}/discriminator.pth')
        print(f"[GANTrainer] 模型已保存到 {save_dir}")

    def load_models(self, save_dir='./models'):
        """加载模型"""
        self.generator.load_state_dict(torch.load(f'{save_dir}/generator.pth'))
        self.discriminator.load_state_dict(torch.load(f'{save_dir}/discriminator.pth'))
        print(f"[GANTrainer] 模型已从 {save_dir} 加载")


# ============================================================
# 图片生成器
# ============================================================

class ImageGenerator:
    """
    图片生成器

    使用方法:
        generator = ImageGenerator(latent_dim=100)
        generator.load_model('./models/generator.pth')
        images = generator.generate(num_images=10)
    """

    def __init__(self, latent_dim=100, device=None):
        """
        初始化生成器

        Args:
            latent_dim: 隐变量维度
            device: 设备 (cuda/cpu)
        """
        self.latent_dim = latent_dim
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        self.model = Generator(latent_dim).to(self.device)
        self.model.eval()

        print(f"[ImageGenerator] 初始化完成 - 设备: {self.device}")

    def load_model(self, model_path):
        """
        加载训练好的生成器模型

        Args:
            model_path: 模型文件路径
        """
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()
        print(f"[ImageGenerator] 模型已加载: {model_path}")

    def generate(self, num_images=1, seed=None):
        """
        生成图片

        Args:
            num_images: 生成图片数量
            seed: 随机种子（可选）

        Returns:
            生成的图片 numpy array (num_images, 32, 32, 3)
        """
        if seed is not None:
            torch.manual_seed(seed)

        with torch.no_grad():
            # 生成随机噪声
            z = torch.randn(num_images, self.latent_dim).to(self.device)

            # 生成图片
            fake_images = self.model(z)

            # 转换为 numpy
            fake_images = fake_images.cpu().numpy()

            # 从 [-1, 1] 转换到 [0, 255]
            fake_images = ((fake_images + 1) / 2 * 255).astype(np.uint8)

            # 转换维度 (N, C, H, W) -> (N, H, W, C)
            fake_images = np.transpose(fake_images, (0, 2, 3, 1))

        print(f"[ImageGenerator] 已生成 {num_images} 张图片")
        return fake_images

    def save_images(self, images, save_dir='./generated'):
        """
        保存生成的图片

        Args:
            images: 图片数组 (N, H, W, C)
            save_dir: 保存目录
        """
        import matplotlib.pyplot as plt

        os.makedirs(save_dir, exist_ok=True)

        for i, img in enumerate(images):
            plt.imsave(f'{save_dir}/generated_{i:04d}.png', img)

        print(f"[ImageGenerator] {len(images)} 张图片已保存到 {save_dir}")


# ============================================================
# 分布式图片生成 Worker
# ============================================================

try:
    import miniray

    @miniray.remote
    class ImageGeneratorWorker:
        """
        分布式图片生成 Worker

        用于并行生成大量图片
        """

        def __init__(self, worker_id, latent_dim=100, device=None):
            self.worker_id = worker_id
            self.latent_dim = latent_dim
            self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

            self.model = Generator(latent_dim).to(self.device)
            self.model.eval()

            print(f"[GeneratorWorker {worker_id}] 初始化完成 - 设备: {self.device}")

        def load_model(self, model_path):
            """加载训练好的生成器模型"""
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
            self.model.eval()
            print(f"[GeneratorWorker {self.worker_id}] 模型已加载: {model_path}")

        def generate(self, num_images, seed=None):
            """
            生成图片

            Args:
                num_images: 生成图片数量
                seed: 随机种子（可选）

            Returns:
                生成的图片 numpy array (num_images, 32, 32, 3)
            """
            if seed is not None:
                torch.manual_seed(seed + self.worker_id)  # 确保每个 Worker 的种子不同

            with torch.no_grad():
                # 生成随机噪声
                z = torch.randn(num_images, self.latent_dim).to(self.device)

                # 生成图片
                fake_images = self.model(z)

                # 转换为 numpy
                fake_images = fake_images.cpu().numpy()

                # 从 [-1, 1] 转换到 [0, 255]
                fake_images = ((fake_images + 1) / 2 * 255).astype(np.uint8)

                # 转换维度 (N, C, H, W) -> (N, H, W, C)
                fake_images = np.transpose(fake_images, (0, 2, 3, 1))

            print(f"[GeneratorWorker {self.worker_id}] 生成 {num_images} 张图片")
            return fake_images

        def save_images(self, images, save_dir, start_idx=0):
            """
            保存生成的图片

            Args:
                images: 图片数组 (N, H, W, C)
                save_dir: 保存目录
                start_idx: 起始索引（用于避免文件名冲突）

            Returns:
                保存的文件路径列表
            """
            import matplotlib.pyplot as plt

            os.makedirs(save_dir, exist_ok=True)

            saved_files = []
            for i, img in enumerate(images):
                filename = f'{save_dir}/generated_{start_idx + i:04d}.png'
                plt.imsave(filename, img)
                saved_files.append(filename)

            print(f"[GeneratorWorker {self.worker_id}] 保存 {len(images)} 张图片到 {save_dir}")
            return saved_files

except ImportError:
    # 如果 miniray 不可用，跳过分布式 Worker
    ImageGeneratorWorker = None
    print("[Warning] miniray 不可用，分布式生成功能将不可用")

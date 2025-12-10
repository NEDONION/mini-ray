"""
GAN 模型测试

测试 Generator、Discriminator 和 GANTrainer 的基本功能
"""

import pytest
import torch
import torch.nn as nn
import tempfile
import os
import numpy as np
from unittest.mock import patch, MagicMock

from ml.gan.models import Generator, Discriminator, GANTrainer, ImageGenerator


class TestGenerator:
    """Generator 模型测试类"""
    
    def test_generator_initialization(self):
        """测试 Generator 初始化"""
        latent_dim = 100
        generator = Generator(latent_dim=latent_dim)
        
        assert isinstance(generator, nn.Module)
        assert generator.latent_dim == latent_dim
        
        # 检查网络结构
        assert hasattr(generator, 'main')
        assert len(generator.main) == 8  # 检查层数
    
    def test_generator_forward_pass(self):
        """测试 Generator 前向传播"""
        latent_dim = 100
        generator = Generator(latent_dim=latent_dim)
        
        batch_size = 4
        z = torch.randn(batch_size, latent_dim)
        
        output = generator(z)
        
        # 输出应该是 (N, 3, 32, 32) 形状的图像
        assert output.shape == (batch_size, 3, 32, 32)
        # 输出值应该在 [-1, 1] 范围内（因为最后一层是 Tanh）
        assert output.min() >= -1.0
        assert output.max() <= 1.0


class TestDiscriminator:
    """Discriminator 模型测试类"""
    
    def test_discriminator_initialization(self):
        """测试 Discriminator 初始化"""
        discriminator = Discriminator()
        
        assert isinstance(discriminator, nn.Module)
        
        # 检查网络结构
        assert hasattr(discriminator, 'main')
        assert len(discriminator.main) == 8  # 检查层数
    
    def test_discriminator_forward_pass(self):
        """测试 Discriminator 前向传播"""
        discriminator = Discriminator()
        
        batch_size = 4
        images = torch.randn(batch_size, 3, 32, 32)  # CIFAR-10 形状
        
        output = discriminator(images)
        
        # 输出应该是 (N, 1) 形状的真假概率
        assert output.shape == (batch_size, 1)
        # 输出值应该在 [0, 1] 范围内（因为最后一层是 Sigmoid）
        assert output.min() >= 0.0
        assert output.max() <= 1.0


class TestGANTrainer:
    """GANTrainer 测试类"""
    
    def test_gan_trainer_initialization(self):
        """测试 GANTrainer 初始化"""
        latent_dim = 100
        lr = 0.0002
        device = 'cpu'  # 使用 CPU 以确保测试稳定
        
        trainer = GANTrainer(latent_dim=latent_dim, lr=lr, device=device)
        
        assert trainer.latent_dim == latent_dim
        assert trainer.lr == lr
        assert trainer.device == device
        
        # 检查模型和优化器
        assert isinstance(trainer.generator, Generator)
        assert isinstance(trainer.discriminator, Discriminator)
        assert hasattr(trainer, 'optimizer_G')
        assert hasattr(trainer, 'optimizer_D')
        assert isinstance(trainer.criterion, nn.BCELoss)
        
        # 检查模型在正确的设备上
        assert next(trainer.generator.parameters()).is_cuda == ('cuda' in device)
        assert next(trainer.discriminator.parameters()).is_cuda == ('cuda' in device)
    
    def test_get_dataloader(self):
        """测试数据加载器获取"""
        with patch('torchvision.datasets.CIFAR10'):
            trainer = GANTrainer(device='cpu')
            
            batch_size = 32
            dataloader = trainer.get_dataloader(batch_size=batch_size, num_workers=0)
            
            # 简单检查数据加载器是否创建成功
            assert dataloader.batch_size == batch_size
            assert dataloader.num_workers == 0
    
    @pytest.mark.parametrize("latent_dim,lr", [(100, 0.0002), (50, 0.001), (200, 0.0001)])
    def test_gan_trainer_with_different_params(self, latent_dim, lr):
        """测试不同参数下的 GANTrainer 初始化"""
        trainer = GANTrainer(latent_dim=latent_dim, lr=lr, device='cpu')
        
        assert trainer.latent_dim == latent_dim
        assert trainer.lr == lr
        assert trainer.generator.latent_dim == latent_dim


class TestImageGenerator:
    """ImageGenerator 测试类"""
    
    def test_image_generator_initialization(self):
        """测试 ImageGenerator 初始化"""
        latent_dim = 100
        device = 'cpu'
        
        generator = ImageGenerator(latent_dim=latent_dim, device=device)
        
        assert generator.latent_dim == latent_dim
        assert generator.device == device
        assert hasattr(generator, 'model')
        assert generator.model.training == False  # eval() 模式
    
    def test_image_generator_generate(self):
        """测试图片生成"""
        latent_dim = 100
        generator = ImageGenerator(latent_dim=latent_dim, device='cpu')
        
        # 创建一个简单的模型来测试生成
        num_images = 2
        images = generator.generate(num_images=num_images, seed=42)
        
        # 检查生成的图片形状
        assert images.shape == (num_images, 32, 32, 3)
        # 检查数据类型和值范围
        assert images.dtype == np.uint8
        assert images.min() >= 0
        assert images.max() <= 255
    
    def test_image_generator_save(self):
        """测试图片保存"""
        import numpy as np
        
        latent_dim = 100
        generator = ImageGenerator(latent_dim=latent_dim, device='cpu')
        
        # 生成一些测试图片
        num_images = 2
        images = generator.generate(num_images=num_images, seed=42)
        
        # 在临时目录中保存图片
        with tempfile.TemporaryDirectory() as temp_dir:
            generator.save_images(images, save_dir=temp_dir)
            
            # 检查是否生成了文件
            files = os.listdir(temp_dir)
            assert len(files) == num_images
            assert all(f.endswith('.png') for f in files)


# 创建一个简化的训练测试，不实际进行长时间训练
def test_gan_trainer_train_method():
    """测试 GANTrainer 的训练方法（简化的）"""
    import numpy as np
    from unittest.mock import Mock
    
    trainer = GANTrainer(device='cpu')
    
    # 使用 Mock 代替实际的数据加载
    with patch.object(trainer, 'get_dataloader') as mock_get_loader:
        # 创建一个简单的 Mock 数据加载器
        mock_data = [(torch.randn(2, 3, 32, 32), torch.randint(0, 10, (2,)))]
        mock_loader = Mock()
        mock_loader.__len__ = Mock(return_value=1)
        mock_loader.__iter__ = Mock(return_value=iter(mock_data))
        mock_get_loader.return_value = mock_loader
        
        # 收集器 Mock
        collector = Mock()
        job_id = 'test-job'
        
        # 只运行1个epoch进行测试
        history = trainer.train(epochs=1, batch_size=2, job_id=job_id, collector=collector)
        
        # 检查返回的历史记录
        assert 'g_loss' in history
        assert 'd_loss' in history
        assert 'epochs' in history
        assert len(history['g_loss']) == 1  # 1个epoch
        assert len(history['d_loss']) == 1  # 1个epoch
        assert len(history['epochs']) == 1  # 1个epoch
        assert isinstance(history['g_loss'][0], float)
        assert isinstance(history['d_loss'][0], float)
        
        # 检查收集器是否被调用
        assert collector.record_training_job.called
        assert collector.add_training_log.called


if __name__ == "__main__":
    pytest.main([__file__])
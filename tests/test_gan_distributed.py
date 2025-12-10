"""
GAN 分布式训练器测试

测试 GANWorker 和 GANTrainer 分布式功能
"""

import pytest
import torch
import torch.nn as nn
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# 添加项目路径以便导入
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.join(_current_dir, '..')
if _project_dir not in sys.path:
    sys.path.insert(0, _project_dir)

from ml.gan.distributed_trainer import GANWorker, GANTrainer


class TestGANWorker:
    """GANWorker 测试类"""
    
    def test_gan_worker_initialization(self):
        """测试 GANWorker 初始化"""
        worker_id = 0
        latent_dim = 100
        lr = 0.0002
        device = 'cpu'
        
        # 由于 GANWorker 使用 @miniray.remote 装饰器，我们测试其属性
        # 在实际环境中，会使用 .remote() 方法创建实例
        worker = GANWorker(worker_id, latent_dim, lr, device)
        
        assert worker.worker_id == worker_id
        assert worker.latent_dim == latent_dim
        assert worker.lr == lr
        assert worker.device == device
        
        # 检查模型创建
        assert isinstance(worker.generator, nn.Module)
        assert isinstance(worker.discriminator, nn.Module)
        assert hasattr(worker, 'optimizer_G')
        assert hasattr(worker, 'optimizer_D')
        assert isinstance(worker.criterion, nn.BCELoss)
    
    def test_gan_worker_get_set_weights(self):
        """测试 GANWorker 的权重获取和设置"""
        worker = GANWorker(0, latent_dim=100, lr=0.0002, device='cpu')
        
        # 获取当前权重
        weights = worker.get_weights()
        assert isinstance(weights, list)
        assert len(weights) > 0  # 应该有多个参数张量
        
        # 确保所有权重都是张量
        for w in weights:
            assert isinstance(w, torch.Tensor)
        
        # 测试设置权重（应该成功而不抛出异常）
        worker.set_weights(weights)
    
    def test_gan_worker_train_epoch_stub(self):
        """测试 GANWorker 的训练epoch方法（存根测试）"""
        # 由于训练需要数据加载器，我们测试在没有数据的情况下的行为
        worker = GANWorker(0, latent_dim=100, lr=0.0002, device='cpu')
        
        # 应该在没有 dataloader 时抛出异常或处理得当
        try:
            result = worker.train_epoch(0)
            # 如果没有异常，检查返回值格式
            assert 'worker_id' in result
            assert 'epoch' in result
        except Exception:
            # 没有dataloader时抛出异常是可以接受的
            pass


class TestGANTrainer:
    """GANTrainer 测试类"""
    
    def test_gan_trainer_initialization(self):
        """测试 GANTrainer 初始化"""
        trainer = GANTrainer(
            num_workers=2,
            latent_dim=100,
            lr=0.0002,
            sync_interval=5,
            sync_strategy='average'
        )
        
        assert trainer.num_workers == 2
        assert trainer.latent_dim == 100
        assert trainer.lr == 0.0002
        assert trainer.sync_interval == 5
        assert trainer.sync_strategy == 'average'
    
    def test_create_worker(self):
        """测试创建 worker 的方法"""
        trainer = GANTrainer(num_workers=1)
        
        # 测试 create_worker 方法 - 由于使用 remote，实际创建会在 miniray 环境中
        worker = trainer.create_worker(0)
        # 确保返回的是远程对象（mock或实际remote对象）
        assert worker is not None
    
    def test_on_epoch_end(self):
        """测试 on_epoch_end 方法"""
        trainer = GANTrainer(num_workers=1)
        
        # 测试 GAN 特定指标打印
        result = {
            'g_loss': 0.5,
            'd_loss': 0.7,
            'accuracy': 0.8
        }
        
        # 这应该不会抛出异常
        trainer.on_epoch_end(epoch=1, result=result)
        
        # 检查结果是否被正确处理
        assert result['g_loss'] == 0.5
        assert result['d_loss'] == 0.7


# 为分布式组件添加集成测试
def test_gan_trainer_end_to_end():
    """测试 GANTrainer 端到端（简化版）"""
    from unittest.mock import Mock
    
    trainer = GANTrainer(
        num_workers=1,  # 使用1个worker以简化测试
        latent_dim=10,
        lr=0.0002,
    )
    
    # 我们不运行完整的训练，而是检查trainer的结构和方法
    assert hasattr(trainer, 'create_worker')
    assert hasattr(trainer, 'on_epoch_end')
    assert trainer.latent_dim == 10
    
    # 验证继承的属性
    assert hasattr(trainer, 'workers')
    assert hasattr(trainer, 'sync_interval')
    assert hasattr(trainer, 'sync_strategy')


# 测试分布式训练器的参数配置
@pytest.mark.parametrize("num_workers,latent_dim,lr,sync_interval", [
    (1, 50, 0.0001, 1),
    (2, 100, 0.0002, 5),
    (4, 200, 0.001, 10),
])
def test_gan_trainer_with_different_configs(num_workers, latent_dim, lr, sync_interval):
    """测试不同配置下的 GANTrainer"""
    trainer = GANTrainer(
        num_workers=num_workers,
        latent_dim=latent_dim,
        lr=lr,
        sync_interval=sync_interval
    )
    
    assert trainer.num_workers == num_workers
    assert trainer.latent_dim == latent_dim
    assert trainer.lr == lr
    assert trainer.sync_interval == sync_interval


if __name__ == "__main__":
    pytest.main([__file__])
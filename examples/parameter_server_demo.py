"""
ParameterServer 使用示例

演示如何使用轻量级 ParameterServer 进行分布式训练
"""

import sys
import os

# 导入 miniray
_current_dir = os.path.dirname(os.path.abspath(__file__))
_python_path = os.path.join(_current_dir, '..', 'python')
if _python_path not in sys.path:
    sys.path.insert(0, _python_path)

import miniray
import torch
import torch.nn as nn
from miniray.ps import create_parameter_server


# ============================================================
# 示例 1: 简单的线性模型 Worker
# ============================================================

@miniray.remote
class SimpleWorker:
    """简单的训练 Worker（示例）"""

    def __init__(self, worker_id):
        self.worker_id = worker_id
        # 简单的线性模型
        self.model = nn.Linear(10, 1)
        self.optimizer = torch.optim.SGD(self.model.parameters(), lr=0.01)

    def train_step(self):
        """模拟训练一步"""
        # 模拟数据
        x = torch.randn(32, 10)
        y = torch.randn(32, 1)

        # 前向 + 反向
        self.optimizer.zero_grad()
        loss = nn.functional.mse_loss(self.model(x), y)
        loss.backward()
        self.optimizer.step()

        return {"worker_id": self.worker_id, "loss": loss.item()}

    def get_weights(self):
        """获取模型参数"""
        return [p.detach().cpu() for p in self.model.parameters()]

    def set_weights(self, weights):
        """设置模型参数"""
        with torch.no_grad():
            for param, new_weight in zip(self.model.parameters(), weights):
                param.copy_(new_weight)


# ============================================================
# 示例 2: 使用不同的同步策略
# ============================================================

def demo_average_strategy():
    """演示：平均策略（最常用）"""
    print("\n" + "=" * 60)
    print("示例 1: 平均策略 (AverageStrategy)")
    print("=" * 60)

    miniray.init(num_workers=4)

    # 创建 ParameterServer - 平均策略
    ps = create_parameter_server('average')

    # 创建 Workers
    workers = [SimpleWorker.remote(i) for i in range(4)]

    # 训练 10 步
    for step in range(10):
        # 并行训练
        results = miniray.get([w.train_step.remote() for w in workers])

        avg_loss = sum(r['loss'] for r in results) / len(results)
        print(f"Step {step}: Loss = {avg_loss:.4f}")

        # 每 3 步同步一次
        if (step + 1) % 3 == 0:
            ps.sync_from_workers.remote(workers)
            stats = miniray.get(ps.get_stats.remote())
            print(f"  ✅ 参数同步完成 (版本: {stats['version']})")

    miniray.shutdown()


def demo_momentum_strategy():
    """演示：动量策略"""
    print("\n" + "=" * 60)
    print("示例 2: 动量策略 (MomentumStrategy)")
    print("=" * 60)

    miniray.init(num_workers=4)

    # 创建 ParameterServer - 动量策略
    ps = create_parameter_server('momentum', momentum=0.9)

    workers = [SimpleWorker.remote(i) for i in range(4)]

    for step in range(10):
        results = miniray.get([w.train_step.remote() for w in workers])
        avg_loss = sum(r['loss'] for r in results) / len(results)
        print(f"Step {step}: Loss = {avg_loss:.4f}")

        if (step + 1) % 3 == 0:
            ps.sync_from_workers.remote(workers)
            stats = miniray.get(ps.get_stats.remote())
            print(f"  ✅ 参数同步完成 (版本: {stats['version']}, 策略: 动量)")

    miniray.shutdown()


def demo_weighted_strategy():
    """演示：加权平均策略（按样本数量加权）"""
    print("\n" + "=" * 60)
    print("示例 3: 加权平均策略 (WeightedAverageStrategy)")
    print("=" * 60)

    miniray.init(num_workers=4)

    # 创建 ParameterServer - 加权策略
    ps = create_parameter_server('weighted')

    # 设置各 Worker 的权重（模拟不同数据量）
    # Worker 0 有 100 个样本，Worker 1 有 200 个样本，等等
    miniray.get(ps.set_worker_weight.remote(0, 100))
    miniray.get(ps.set_worker_weight.remote(1, 200))
    miniray.get(ps.set_worker_weight.remote(2, 150))
    miniray.get(ps.set_worker_weight.remote(3, 250))

    workers = [SimpleWorker.remote(i) for i in range(4)]

    for step in range(10):
        results = miniray.get([w.train_step.remote() for w in workers])
        avg_loss = sum(r['loss'] for r in results) / len(results)
        print(f"Step {step}: Loss = {avg_loss:.4f}")

        if (step + 1) % 3 == 0:
            ps.sync_from_workers.remote(workers)
            stats = miniray.get(ps.get_stats.remote())
            print(f"  ✅ 参数同步完成 (版本: {stats['version']}, 策略: 加权平均)")

    miniray.shutdown()


# ============================================================
# 示例 3: 在 GAN 训练中使用
# ============================================================

def demo_gan_training():
    """演示：在 GAN 训练中使用 ParameterServer"""
    print("\n" + "=" * 60)
    print("示例 4: GAN 训练中使用 ParameterServer")
    print("=" * 60)

    from ml.distributed_gan import DistributedGANTrainer

    # 使用平均策略
    trainer = DistributedGANTrainer(
        num_workers=4,
        latent_dim=100,
        lr=0.0002,
        sync_strategy='average'  # 可选: 'momentum', 'weighted'
    )

    print("\n开始训练（仅演示，epochs=2）...")
    try:
        history, workers = trainer.train(
            epochs=2,
            batch_size=128,
            sync_interval=1  # 每个 epoch 都同步
        )
        print("\n✅ 训练完成!")
    except Exception as e:
        print(f"\n⚠️  训练需要 CIFAR-10 数据集: {e}")


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "=" * 60)
    print("ParameterServer 使用示例")
    print("=" * 60)

    # 运行各个示例
    demo_average_strategy()
    demo_momentum_strategy()
    demo_weighted_strategy()

    # GAN 训练示例（可选）
    # demo_gan_training()

    print("\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()

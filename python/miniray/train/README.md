# Mini-Ray Train - 轻量级分布式训练框架

通用的分布式训练抽象，避免重复编写训练循环代码。

## ✨ 特点

- ✅ **通用**：支持任意模型（GAN、ResNet、BERT、分类、回归等）
- ✅ **轻量**：~200 行核心代码，无额外依赖
- ✅ **简洁**：将 200+ 行训练代码减少到 20 行
- ✅ **灵活**：支持完全自定义训练流程
- ✅ **集成**：自动集成 ParameterServer 进行参数同步

## 🎯 解决的问题

### ❌ 修改前：重复的训练代码

每次写新模型都要重复这些逻辑：

```python
# DistributedGANTrainer（~250 行）
class DistributedGANTrainer:
    def train(self, epochs):
        # 1. 初始化 Mini-Ray
        miniray.init(num_workers=self.num_workers)

        # 2. 创建 Workers
        workers = [...]

        # 3. 数据分片
        miniray.get([w.load_data_shard.remote(...)])

        # 4. 训练循环
        for epoch in range(epochs):
            results = miniray.get([w.train_epoch.remote(epoch) for w in workers])

            # 5. 聚合结果
            avg_loss = np.mean([r["loss"] for r in results])

            # 6. 参数同步
            if (epoch + 1) % sync_interval == 0:
                # 15 行同步代码...

        # 7. 清理
        miniray.shutdown()
```

**问题**：
- 每个新模型都要复制这 200+ 行代码
- 同样的 bug 会重复出现（参数顺序、类型处理、同步时机...）
- 难以维护和升级

### ✅ 修改后：使用 DataParallelTrainer

```python
# 只需 20 行！
class GANTrainer(DataParallelTrainer):
    def create_worker(self, worker_id, **kwargs):
        return GANWorker.remote(worker_id, self.latent_dim, self.lr)

    def on_epoch_end(self, epoch, result, **kwargs):
        print(f"G_loss: {result['g_loss']:.4f}, D_loss: {result['d_loss']:.4f}")

# 使用
trainer = GANTrainer(num_workers=4, sync_interval=5)
trainer.train(epochs=50, batch_size=128)
```

**优势**：
- ✅ 代码量减少 **90%**
- ✅ 数据分片、参数同步、训练循环全部自动处理
- ✅ Bug 修复一次，所有模型受益
- ✅ 易于维护和扩展

## 📦 快速开始

### 1. 定义 Worker（需实现 3 个方法）

```python
import miniray

@miniray.remote
class MyWorker:
    def __init__(self, worker_id):
        self.model = ...  # 你的模型
        self.optimizer = ...

    # 必需方法 1：训练一个 epoch
    def train_epoch(self, epoch):
        # 训练逻辑...
        return {"loss": loss.item(), "accuracy": acc}

    # 必需方法 2：获取模型参数
    def get_weights(self):
        return [p.detach().cpu() for p in self.model.parameters()]

    # 必需方法 3：设置模型参数
    def set_weights(self, weights):
        with torch.no_grad():
            for param, new_weight in zip(self.model.parameters(), weights):
                param.copy_(new_weight)

    # 可选方法：加载数据分片
    def load_data_shard(self, shard_id, num_shards, **kwargs):
        # 加载第 shard_id 个数据分片...
        pass
```

### 2. 定义 Trainer（继承 DataParallelTrainer）

```python
from miniray.train import DataParallelTrainer

class MyTrainer(DataParallelTrainer):
    def create_worker(self, worker_id, **kwargs):
        return MyWorker.remote(worker_id)

    # 可选：自定义 epoch 结束处理
    def on_epoch_end(self, epoch, result, **kwargs):
        super().on_epoch_end(epoch, result, **kwargs)
        print(f"Loss: {result['loss']:.4f}")
```

### 3. 训练！

```python
trainer = MyTrainer(
    num_workers=4,
    sync_interval=5,      # 每 5 个 epoch 同步参数
    sync_strategy='average'  # 参数聚合策略
)

result = trainer.train(epochs=50, batch_size=128)
trainer.shutdown()
```

## 🏗️ 架构设计

### 类层次结构

```
BaseTrainer                    # 基类：管理训练循环、Worker 生命周期
    ├── DataParallelTrainer   # 数据并行：自动分片、参数同步
    └── YourCustomTrainer     # 自定义：完全控制训练流程
```

### BaseTrainer（基类）

职责：
- 管理 Mini-Ray 生命周期（init/shutdown）
- Worker 创建和管理
- 训练循环框架（epoch loop）
- 钩子方法（on_epoch_start, on_epoch_end 等）

**关键方法**：

```python
class BaseTrainer:
    def train(self, epochs, **kwargs):
        """训练主循环"""

    def create_worker(self, worker_id, **kwargs):
        """创建 Worker（子类必须实现）"""

    def train_epoch(self, epoch, **kwargs):
        """训练一个 epoch（子类可重写）"""

    # 钩子方法（子类可选实现）
    def on_train_start(self, **kwargs): ...
    def on_train_end(self, history, **kwargs): ...
    def on_epoch_start(self, epoch, **kwargs): ...
    def on_epoch_end(self, epoch, result, **kwargs): ...
```

### DataParallelTrainer（数据并行）

职责：
- 自动数据分片（调用 Worker 的 `load_data_shard`）
- 参数同步（使用 ParameterServer）
- 结果聚合（对数值字段取平均）

**额外参数**：

```python
class DataParallelTrainer(BaseTrainer):
    def __init__(
        self,
        num_workers=4,
        sync_interval=1,           # 参数同步间隔
        sync_strategy='average',   # 聚合策略
        **strategy_kwargs          # 策略参数
    ):
        ...
```

**额外方法**：

```python
def set_worker_weight(self, worker_id, weight):
    """设置 Worker 权重（用于加权平均）"""

def get_sync_stats(self):
    """获取参数同步统计"""
```

## 📚 完整示例

### 示例 1：GAN 训练

```python
from miniray.train import DataParallelTrainer

class GANTrainer(DataParallelTrainer):
    def __init__(self, num_workers=4, latent_dim=100, lr=0.0002):
        super().__init__(num_workers=num_workers, sync_interval=5)
        self.latent_dim = latent_dim
        self.lr = lr

    def create_worker(self, worker_id, **kwargs):
        return GANWorker.remote(worker_id, self.latent_dim, self.lr)

    def on_epoch_end(self, epoch, result, **kwargs):
        super().on_epoch_end(epoch, result, **kwargs)
        print(f"  G_loss: {result['g_loss']:.4f}, D_loss: {result['d_loss']:.4f}")

# 使用
trainer = GANTrainer(num_workers=4)
trainer.train(epochs=50, batch_size=128)
```

完整代码：`ml/distributed_gan_v2.py`

### 示例 2：分类模型训练

```python
class ClassificationTrainer(DataParallelTrainer):
    def __init__(self, num_workers=4, lr=0.01):
        super().__init__(num_workers=num_workers, sync_interval=3)
        self.lr = lr

    def create_worker(self, worker_id, **kwargs):
        return ClassificationWorker.remote(worker_id, lr=self.lr)

    def on_epoch_end(self, epoch, result, **kwargs):
        super().on_epoch_end(epoch, result, **kwargs)
        print(f"  Accuracy: {result['accuracy']:.2%}")

# 使用
trainer = ClassificationTrainer(num_workers=4)
trainer.train(epochs=20, dataset='cifar10')
```

完整代码：`examples/train_framework_demo.py`

### 示例 3：自定义训练流程（BaseTrainer）

```python
from miniray.train import BaseTrainer

class CustomTrainer(BaseTrainer):
    def create_worker(self, worker_id, **kwargs):
        return CustomWorker.remote(worker_id)

    def train_epoch(self, epoch, **kwargs):
        # 完全自定义训练逻辑
        results = miniray.get([
            w.custom_method.remote(epoch) for w in self.workers
        ])
        return {"custom_metric": sum(results) / len(results)}

# 使用
trainer = CustomTrainer(num_workers=4)
trainer.train(epochs=10)
```

### 示例 4：使用 with 语句

```python
with ClassificationTrainer(num_workers=4) as trainer:
    result = trainer.train(epochs=10)
    print("训练完成！")
# Mini-Ray 自动关闭
```

## 🎨 高级用法

### 1. 自定义结果聚合

```python
class MyTrainer(DataParallelTrainer):
    def train_epoch(self, epoch, **kwargs):
        worker_results = miniray.get([
            w.train_epoch.remote(epoch) for w in self.workers
        ])

        # 自定义聚合逻辑
        aggregated = {
            'loss': np.median([r['loss'] for r in worker_results]),  # 中位数
            'max_acc': max(r['accuracy'] for r in worker_results),   # 最大值
        }

        # 参数同步（继承的逻辑）
        if (epoch + 1) % self.sync_interval == 0:
            self.param_server.sync_from_workers.remote(self.workers)
            aggregated['synced'] = True

        return aggregated
```

### 2. 加权平均策略

```python
trainer = DataParallelTrainer(
    num_workers=4,
    sync_strategy='weighted'  # 使用加权平均
)

# 设置各 Worker 的权重（如样本数量）
trainer.set_worker_weight(0, 1000)
trainer.set_worker_weight(1, 2000)
trainer.set_worker_weight(2, 1500)
trainer.set_worker_weight(3, 2500)

trainer.train(epochs=50)
```

### 3. 动量策略

```python
trainer = DataParallelTrainer(
    num_workers=4,
    sync_strategy='momentum',
    momentum=0.9  # 策略参数
)

trainer.train(epochs=50)
```

### 4. 钩子方法使用

```python
class MyTrainer(DataParallelTrainer):
    def on_train_start(self, **kwargs):
        print("训练开始，初始化...")
        # 自定义初始化逻辑

    def on_epoch_start(self, epoch, **kwargs):
        print(f"Epoch {epoch} 开始")
        # Epoch 开始时的操作

    def on_epoch_end(self, epoch, result, **kwargs):
        super().on_epoch_end(epoch, result, **kwargs)
        # 保存检查点
        if (epoch + 1) % 10 == 0:
            self.save_checkpoint(epoch)

    def on_train_end(self, history, **kwargs):
        result = super().on_train_end(history, **kwargs)
        # 保存最终模型
        self.save_final_model()
        return result
```

## 📊 性能优化

### 1. 调整同步间隔

```python
# 频繁同步：参数更一致，但开销大
trainer = DataParallelTrainer(sync_interval=1)

# 稀疏同步：开销小，但参数可能发散
trainer = DataParallelTrainer(sync_interval=10)

# 推荐：5-10
trainer = DataParallelTrainer(sync_interval=5)
```

### 2. Worker 数量

```python
# Worker 数量 = CPU 核心数 / 2（推荐）
import os
num_workers = os.cpu_count() // 2

trainer = DataParallelTrainer(num_workers=num_workers)
```

### 3. 批量大小

```python
# 总批量大小 = batch_size * num_workers
# 建议保持总批量大小不变，调整 batch_size
total_batch = 512
num_workers = 4
batch_size = total_batch // num_workers  # 128

trainer.train(epochs=50, batch_size=batch_size)
```

## 🔄 与原始代码对比

| 特性 | 原始代码（DistributedGANTrainer） | 使用 Train 框架 |
|------|----------------------------------|-----------------|
| 代码量 | ~250 行 | ~20 行 |
| 数据分片 | 手动实现 | 自动处理 |
| 参数同步 | 手动实现（15 行） | 自动处理（1 行）|
| 结果聚合 | 手动实现 | 自动处理 |
| 训练循环 | 手动实现 | 自动处理 |
| 生命周期管理 | 手动 init/shutdown | 自动管理 |
| 可扩展性 | 低（需复制代码）| 高（继承扩展）|
| 可维护性 | 低（分散在各处）| 高（集中管理）|

## 🐛 常见问题

**Q: Worker 必须实现哪些方法？**

A:
- 必需：`train_epoch(epoch)`, `get_weights()`, `set_weights(weights)`
- 可选：`load_data_shard(shard_id, num_shards, **kwargs)`

**Q: 如何传递参数给 Worker？**

A: 通过 `create_worker()` 方法：

```python
def create_worker(self, worker_id, **kwargs):
    lr = kwargs.get('lr', 0.01)
    return MyWorker.remote(worker_id, lr=lr)

trainer.train(epochs=50, lr=0.001)  # 传递给 create_worker
```

**Q: 如何自定义训练循环？**

A: 继承 BaseTrainer 并重写 `train_epoch()` 方法。

**Q: 支持多 GPU 训练吗？**

A: 支持。在 Worker 中指定 device，参数同步在 CPU 上进行。

**Q: 如何保存模型？**

A: 在 `on_epoch_end()` 或 `on_train_end()` 中调用 Worker 的保存方法。

## 📈 路线图

- [x] BaseTrainer - 通用训练循环
- [x] DataParallelTrainer - 数据并行
- [x] ParameterServer 集成
- [ ] ModelParallelTrainer - 模型并行（未来）
- [ ] PipelineParallelTrainer - 流水线并行（未来）
- [ ] 检查点和恢复（未来）
- [ ] 分布式评估（未来）

## 📖 更多资源

- **完整示例**: `examples/train_framework_demo.py`
- **GAN 训练**: `ml/distributed_gan_v2.py`
- **ParameterServer 文档**: `python/miniray/ps/README.md`

## 📄 许可证

MIT License

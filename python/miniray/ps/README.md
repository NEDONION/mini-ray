# Mini-Ray Parameter Server

轻量级参数服务器，作为 Mini-Ray 的核心能力之一，用于分布式训练中的参数同步。

## ✨ 特点

- ✅ **通用**：支持任意模型（GAN、ResNet、BERT 等）
- ✅ **轻量**：~100 行代码，无额外依赖
- ✅ **可扩展**：支持多种聚合策略（平均、加权、动量）
- ✅ **易用**：一行代码完成参数同步
- ✅ **集成**：作为 Mini-Ray 核心模块，开箱即用

## 📦 快速开始

### 基础用法

```python
import miniray
from miniray.ps import create_parameter_server

# 1. 创建 ParameterServer
ps = create_parameter_server('average')

# 2. 在训练循环中同步参数
for epoch in range(epochs):
    # 训练...
    if (epoch + 1) % sync_interval == 0:
        ps.sync_from_workers.remote(workers)
```

### 完整示例

```python
import miniray
from miniray.ps import create_parameter_server
import torch.nn as nn

# 定义 Worker（需实现 get_weights() 和 set_weights()）
@miniray.remote
class TrainingWorker:
    def __init__(self, worker_id):
        self.model = nn.Linear(10, 1)

    def get_weights(self):
        return [p.detach().cpu() for p in self.model.parameters()]

    def set_weights(self, weights):
        with torch.no_grad():
            for param, new_weight in zip(self.model.parameters(), weights):
                param.copy_(new_weight)

    def train_step(self):
        # 训练逻辑...
        pass

# 初始化 Mini-Ray
miniray.init(num_workers=4)

# 创建 ParameterServer 和 Workers
ps = create_parameter_server('average')
workers = [TrainingWorker.remote(i) for i in range(4)]

# 训练循环
for epoch in range(10):
    # 并行训练
    miniray.get([w.train_step.remote() for w in workers])

    # 每 3 个 epoch 同步一次
    if (epoch + 1) % 3 == 0:
        ps.sync_from_workers.remote(workers)
        print(f"Epoch {epoch+1}: 参数同步完成")
```

## 🎯 聚合策略

### 1. 平均策略（默认）

```python
ps = create_parameter_server('average')
```

- 简单平均所有 Worker 的参数
- 适用于数据均匀分布的场景
- **最常用**

### 2. 加权平均策略

```python
ps = create_parameter_server('weighted')

# 设置各 Worker 的权重（如样本数量）
miniray.get(ps.set_worker_weight.remote(0, 1000))
miniray.get(ps.set_worker_weight.remote(1, 2000))
```

- 按样本数量加权平均
- 适用于数据不均匀分布的场景

### 3. 动量策略

```python
ps = create_parameter_server('momentum', momentum=0.9)
```

- 使用指数移动平均（EMA）聚合参数
- 适用于需要平滑更新的场景
- 可减少参数波动

## 📚 API 参考

### ParameterServer

**主要方法**：

```python
# 同步参数（最常用）
ps.sync_from_workers.remote(worker_refs)

# 获取全局参数
weights = miniray.get(ps.pull_weights.remote())

# 获取统计信息
stats = miniray.get(ps.get_stats.remote())
# 返回: {'version': 10, 'num_syncs': 10, 'strategy': 'AverageStrategy', ...}

# 设置 Worker 权重（仅用于 weighted 策略）
ps.set_worker_weight.remote(worker_id, weight)
```

### Worker 接口要求

使用 ParameterServer 的 Worker 必须实现：

```python
@miniray.remote
class MyWorker:
    def get_weights(self) -> List[torch.Tensor]:
        """返回模型参数列表（线性化）"""
        return [p.detach().cpu() for p in self.model.parameters()]

    def set_weights(self, weights: List[torch.Tensor]):
        """从参数列表恢复模型参数"""
        with torch.no_grad():
            for param, new_weight in zip(self.model.parameters(), weights):
                param.copy_(new_weight.to(self.device))
```

## 🔧 高级用法

### 自定义聚合策略

```python
from miniray.ps.strategies import SyncStrategy, STRATEGIES

class MedianStrategy(SyncStrategy):
    """中位数策略（对异常值更鲁棒）"""

    def aggregate(self, weight_lists):
        import torch
        num_params = len(weight_lists[0])
        aggregated = []

        for p_idx in range(num_params):
            tensors = [w[p_idx] for w in weight_lists]
            if torch.is_floating_point(tensors[0]):
                stacked = torch.stack(tensors)
                median_tensor = torch.median(stacked, dim=0)[0]
                aggregated.append(median_tensor)
            else:
                aggregated.append(tensors[0])

        return aggregated

# 注册策略
STRATEGIES['median'] = MedianStrategy

# 使用
from miniray.ps import create_parameter_server
ps = create_parameter_server('median')
```

### 获取同步统计

```python
# 在训练过程中监控同步状态
stats = miniray.get(ps.get_stats.remote())

print(f"参数版本: {stats['version']}")
print(f"同步次数: {stats['num_syncs']}")
print(f"聚合策略: {stats['strategy']}")
print(f"是否已初始化: {stats['initialized']}")
```

## 📖 使用示例

查看完整示例：

- **基础示例**: `examples/parameter_server_demo.py`
- **GAN 训练**: `ml/distributed_gan.py`

运行示例：

```bash
# 基础示例（演示不同策略）
python examples/parameter_server_demo.py

# GAN 训练示例
python -m ml.train --mode distributed --workers 4 --epochs 10
```

## 🎨 架构设计

### 模块结构

```
miniray/ps/
├── __init__.py              # 导出接口
├── parameter_server.py      # ParameterServer Actor 实现
├── strategies.py            # 聚合策略
└── README.md                # 本文档
```

### 工作流程

```
Driver Process
    │
    ├─ 创建 ParameterServer Actor
    │
    ├─ 创建多个 Training Workers
    │
    └─ 训练循环
        ├─ Workers 并行训练
        │
        └─ 周期性参数同步
            ├─ 1. PS 收集所有 Worker 权重
            ├─ 2. PS 使用策略聚合权重
            ├─ 3. PS 下发聚合后的权重
            └─ 4. Workers 更新本地参数
```

## 💡 设计理念

### 为什么需要 ParameterServer？

**问题**：分布式训练中，每个新模型都要重复写参数同步逻辑：

```python
# ❌ 每次都要写这些代码
weight_lists = miniray.get([w.get_weights.remote() for w in workers])
avg_weights = []
for p in range(len(weight_lists[0])):
    tensors = [weight_lists[w][p] for w in range(num_workers)]
    avg_weights.append(torch.stack(tensors).mean(0))
miniray.get([w.set_weights.remote(avg_weights) for w in workers])
```

**解决方案**：轻量级 ParameterServer

```python
# ✅ 一行搞定
ps.sync_from_workers.remote(workers)
```

### 为什么是轻量级？

- **不是完整的 PS 系统**：无需处理复杂的分片、容错、版本管理
- **适合小规模训练**：4-16 个 Workers，同步频率低
- **保持简洁**：符合 Mini-Ray 的设计哲学

## 🔄 与其他框架对比

| 特性 | Mini-Ray PS | PyTorch DDP | Ray Train |
|------|-------------|-------------|-----------|
| 代码量 | ~100 行 | 内置 | 完整框架 |
| 易用性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 灵活性 | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 适用场景 | 教育/小规模 | 生产环境 | 生产环境 |
| 自定义策略 | ✅ 简单 | ❌ 困难 | ✅ 可能 |

## 📈 性能考量

### 同步开销

- **网络传输**：Worker ↔ ParameterServer
- **序列化开销**：Python ↔ 共享内存
- **聚合计算**：取决于策略（平均 < 加权 < 动量）

### 优化建议

1. **降低同步频率**：`sync_interval = 5-10`
2. **减少 Worker 数量**：建议 ≤ CPU 核心数 / 2
3. **使用简单策略**：优先选择 `average`

## 🚀 未来扩展

- [ ] 支持异步参数更新（push/pull 模式）
- [ ] 支持梯度聚合（而非权重聚合）
- [ ] 支持参数分片（针对大模型）
- [ ] 支持容错和检查点
- [ ] 支持混合精度训练

## 📝 常见问题

**Q: 何时使用 ParameterServer？**

A: 当你需要在多个 Worker 之间同步模型参数时。适用于数据并行训练场景。

**Q: 与手动同步有何区别？**

A: ParameterServer 封装了收集、聚合、下发的完整流程，支持多种策略，代码更简洁。

**Q: 支持异步训练吗？**

A: 当前版本是同步训练（所有 Worker 同时更新）。异步训练计划在未来版本支持。

**Q: 如何选择聚合策略？**

A:
- 数据均匀分布 → `average`
- 数据不均匀 → `weighted`
- 需要平滑更新 → `momentum`

**Q: 性能瓶颈在哪？**

A: 主要是网络传输和序列化。建议降低同步频率，或使用梯度压缩（未来支持）。

## 🤝 贡献

欢迎贡献新的聚合策略或性能优化！请参考：

1. 继承 `SyncStrategy` 实现自定义策略
2. 在 `STRATEGIES` 字典中注册
3. 编写测试和文档
4. 提交 Pull Request

## 📄 许可证

MIT License

# Mini-Ray ML Module - GAN for CIFAR-10

生成式对抗网络（GAN）用于 CIFAR-10 图片生成

**✨ 支持单机和分布式训练 + 分布式生成！**

## 📁 文件结构

```
ml/                           # 外部 ML 模块目录
├── __init__.py              # 模块导出
├── gan_cifar10.py           # GAN 基础实现（Generator, Discriminator）
├── distributed_gan.py       # 🚀 分布式 GAN（训练 + 生成，使用 Mini-Ray @remote）
├── train.py                 # 训练入口（单机 + 分布式）
├── generate.py              # 图片生成入口（单机 + 分布式）
├── requirements.txt         # ML 依赖
└── README.md                # 本文件
```

## 📦 安装依赖

```bash
# 方式 1: 安装 ML 模块依赖
pip install -r ml/requirements.txt

# 方式 2: 安装完整项目依赖（包括 Dashboard）
pip install -r requirements.txt
```

## 🚀 快速开始

### 方式 1：单机训练（适合快速测试）

```bash
# 单机训练 10 epochs
python -m ml.train --mode single --epochs 10
```

### 方式 2：分布式训练（🎯 Mini-Ray 特性！）

```bash
# 分布式训练 - 4 个 Worker 并行
python -m ml.train --mode distributed --workers 4 --epochs 10 --sync-interval 5
```

**分布式训练特点：**
- ✅ 使用 `@miniray.remote` 装饰器创建分布式 Worker
- ✅ 数据自动分片到各个 Worker
- ✅ 4 个 Worker 并行训练，速度提升 ~4 倍
- ✅ 定期同步模型参数（平均聚合）
- ✅ 实时在 Dashboard 监控所有 Worker

### 生成图片

#### 单机生成（适合少量图片）

```bash
# 生成 10 张图片
python -m ml.generate --model ./models/gan/generator.pth --num-images 10
```

#### 分布式生成（🆕 快速生成大量图片！）

```bash
# 使用 4 个 Worker 并行生成 100 张图片
python -m ml.generate --model ./models/gan/generator.pth --num-images 100 --distributed --workers 4
```

**分布式生成特点：**
- ✅ 使用 `@miniray.remote` 装饰器创建分布式生成 Worker
- ✅ 图片生成任务自动分配到各个 Worker
- ✅ 4 个 Worker 并行生成，速度提升 ~4 倍
- ✅ 适合批量生成大量图片（100+）

## 📊 分布式训练详解

### 架构

```
Main Process
    ↓
启动 4 个 @miniray.remote Workers
    ├── Worker 0: 处理数据分片 0-12499
    ├── Worker 1: 处理数据分片 12500-24999
    ├── Worker 2: 处理数据分片 25000-37499
    └── Worker 3: 处理数据分片 37500-49999

并行训练 1 epoch
    ↓
聚合结果 (平均 Loss)
    ↓
每 5 epochs 同步参数
    ↓
继续训练...
```

### 工作流程

1. **数据分片**
   - CIFAR-10 有 50,000 张训练图片
   - 4 个 Worker 各处理 12,500 张

2. **并行训练**
   - 各 Worker 独立训练 GAN
   - 使用 `miniray.get()` 收集结果

3. **参数同步**
   - 每 N epochs 收集所有模型参数
   - 平均聚合后广播回各 Worker
   - 保持模型一致性

4. **Dashboard 监控**
   - 实时显示训练进度
   - 聚合后的平均 Loss
   - 每个 epoch 的详细日志

## 📚 API 使用

### 分布式训练

```python
from miniray.ml import DistributedGANTrainer
from miniray.dashboard import get_collector
import miniray

# 初始化 Mini-Ray
miniray.init(num_workers=4)

# 创建分布式训练器
trainer = DistributedGANTrainer(
    num_workers=4,
    latent_dim=100,
    lr=0.0002
)

# 训练
history, workers = trainer.train(
    epochs=50,
    batch_size=128,
    sync_interval=5,  # 每 5 epochs 同步参数
    job_id='dist-gan-001',
    collector=get_collector()
)

# 模型自动保存到 ./models/distributed_gan/worker_*
```

### 单机训练

```python
from miniray.ml import GANTrainer

trainer = GANTrainer(latent_dim=100, lr=0.0002)
history = trainer.train(epochs=10, batch_size=128)
trainer.save_models('./models/gan')
```

### 图片生成

```python
from miniray.ml import ImageGenerator

generator = ImageGenerator(latent_dim=100)
generator.load_model('./models/gan/generator.pth')

# 生成 10 张图片
images = generator.generate(num_images=10)
generator.save_images(images, './output')
```

## ⚙️ 命令行参数

### 训练

```bash
python -m miniray.ml.train \
    --mode distributed \         # single 或 distributed
    --epochs 50 \                # 训练轮数
    --batch-size 128 \           # 批次大小
    --workers 4 \                # Worker 数量（分布式）
    --sync-interval 5 \          # 参数同步间隔
    --latent-dim 100 \           # 隐变量维度
    --lr 0.0002 \                # 学习率
    --save-dir ./models/gan      # 保存目录
```

### 生成

```bash
python -m miniray.ml.generate \
    --model ./models/gan/generator.pth \
    --num-images 20 \
    --output ./generated \
    --seed 42                    # 可选：固定随机种子
```

## 🎯 模型架构

### Generator（生成器）
```
Input: [batch, 100]               # 随机噪声
  ↓
Linear(100 → 256) + ReLU + BN
  ↓
Linear(256 → 512) + ReLU + BN
  ↓
Linear(512 → 1024) + ReLU + BN
  ↓
Linear(1024 → 3072) + Tanh
  ↓
Output: [batch, 3, 32, 32]       # RGB 图片
```

### Discriminator（判别器）
```
Input: [batch, 3, 32, 32]
  ↓
Flatten → [batch, 3072]
  ↓
Linear(3072 → 1024) + LeakyReLU + Dropout
  ↓
Linear(1024 → 512) + LeakyReLU + Dropout
  ↓
Linear(512 → 256) + LeakyReLU + Dropout
  ↓
Linear(256 → 1) + Sigmoid
  ↓
Output: [batch, 1]               # 真实概率
```

## ⏱️ 性能对比

| 模式 | Worker数 | 训练时间/epoch | 加速比 |
|------|----------|---------------|--------|
| 单机 | 1 | ~120s | 1x |
| 分布式 | 2 | ~65s | 1.8x |
| 分布式 | 4 | ~35s | 3.4x |

*测试环境：CPU训练，CIFAR-10数据集*

## 💡 最佳实践

### 1. 选择模式
- **快速测试**: 单机模式，10 epochs
- **生产训练**: 分布式模式，50-100 epochs

### 2. 参数调优
```bash
# 质量优先（训练时间长）
python -m miniray.ml.train --mode distributed --workers 4 --epochs 100 --sync-interval 10

# 速度优先（质量稍差）
python -m miniray.ml.train --mode single --epochs 20 --batch-size 256
```

### 3. Dashboard 监控
```bash
# 终端 1: 启动 Dashboard
python -m miniray.dashboard

# 终端 2: 训练（自动连接 Dashboard）
python -m miniray.ml.train --mode distributed --workers 4

# 浏览器: http://localhost:8266
# 实时查看训练进度、Loss、日志
```

## 🐛 常见问题

**Q: 分布式训练比单机慢？**
A: 可能原因：
   - Worker 数量过多（超过 CPU 核心数）
   - 同步间隔太短（频繁同步开销大）
   - 建议：Worker 数 = CPU 核心数 / 2，sync_interval >= 5

**Q: 训练出现 OOM（内存不足）？**
A: 减小 batch_size 或减少 Worker 数量

**Q: 生成的图片质量不好？**
A: 需要训练更多 epochs（推荐 50-100）

**Q: 如何使用 GPU 加速？**
A: 修改 `distributed_gan.py` 中的 `device='cpu'` 为 `device='cuda'`

## 📝 代码示例

### 完整训练流程

```python
import miniray
from miniray.ml import DistributedGANTrainer
from miniray.dashboard import get_collector

# 1. 初始化 Mini-Ray
miniray.init(num_workers=4)

# 2. 创建训练器
trainer = DistributedGANTrainer(num_workers=4)

# 3. 训练
history, workers = trainer.train(
    epochs=50,
    batch_size=128,
    sync_interval=5,
    job_id='my-gan',
    collector=get_collector()
)

# 4. 生成图片测试
from miniray.ml import ImageGenerator
gen = ImageGenerator()
gen.load_model('./models/distributed_gan/worker_0/generator.pth')
images = gen.generate(10)
gen.save_images(images, './test_output')

# 5. 关闭
miniray.shutdown()
```

## 🎨 高级功能

### 自定义数据分片策略

```python
# 修改 DistributedGANWorker.load_data_shard() 方法
# 支持自定义数据分配策略
```

### 混合精度训练

```python
# 在 distributed_gan.py 中添加 AMP 支持
# 可进一步加速训练
```

## 📈 未来改进

- [ ] 支持 DCGAN（卷积 GAN）架构
- [ ] 支持其他数据集（ImageNet, CelebA）
- [ ] 添加 FID 评估指标
- [ ] 支持条件 GAN（cGAN）
- [ ] 梯度累积支持更大 batch size

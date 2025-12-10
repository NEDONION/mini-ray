# Mini-Ray Dashboard 模块

Mini-Ray Dashboard 是一个轻量级的 Web 监控界面，用于监控 Mini-Ray 分布式计算框架的运行状态。

## 功能特性

- **任务监控**: 实时监控训练、推理、调优等任务状态
- **系统指标**: 显示 CPU、内存使用情况
- **任务跟踪**: 通过装饰器自动跟踪任务
- **Web 界面**: 简单直观的 Web UI

## 使用方法

### 启动 Dashboard

```bash
# 方式1: 作为模块运行
python -m miniray.dashboard

# 方式2: 通过 Python API
from miniray.dashboard import run_dashboard
run_dashboard(port=8266)
```

访问 `http://localhost:8266` 查看 Dashboard。

### 任务跟踪装饰器（推荐）

使用装饰器可以最简单地将任务注册到 Dashboard 中：

```python
from miniray import track_training_job

@track_training_job(name="My Training Job", description="模型训练任务")
def train_model(epochs):
    # 你的训练代码
    for epoch in range(epochs):
        # 训练逻辑
        pass
    return {"accuracy": 0.95}

# 执行函数，会自动在 Dashboard 中显示任务状态
result = train_model(epochs=10)
```

### 其他任务类型装饰器

```python
from miniray import track_inference_job, track_tuning_job

# 推理任务
@track_inference_job(name="Model Inference", description="模型推理")
def run_inference(data):
    # 推理逻辑
    pass

# 调优任务
@track_tuning_job(name="Hyperparameter Tuning", description="超参数搜索")
def tune_params():
    # 调优逻辑
    pass
```

### 与 Mini-Ray 远程功能集成

```python
import miniray
from miniray import track_training_job

# 结合远程功能和任务跟踪
@miniray.remote
@track_training_job(name="Remote Training", description="远程训练任务")
def remote_train(data):
    # 远程训练逻辑
    return {"result": "completed"}

# 提交远程任务，会自动注册到 Dashboard
ref = remote_train.remote(training_data)
result = miniray.get(ref)
```

## Dashboard API

```python
from miniray.dashboard import get_collector

# 获取指标收集器
collector = get_collector()

# 获取训练任务
training_jobs = collector.get_training_jobs()

# 获取系统统计
stats = collector.get_stats()

# 获取所有任务
tasks = collector.get_tasks()
```

## Dashboard 端点

Dashboard 提供以下 API 端点：

- `GET /` - 主页面
- `GET /api/tasks` - 任务列表
- `GET /api/training-jobs` - 训练任务列表
- `GET /api/workers` - Worker 列表
- `GET /api/stats` - 统计信息
- `GET /api/metrics` - 系统指标

## 优势

- **零侵入性**: 仅需添加装饰器，无需修改业务逻辑
- **实时监控**: 任务状态变化实时更新
- **错误跟踪**: 自动记录失败任务
- **多任务类型**: 支持训练、推理、调优等多种任务
- **集成友好**: 与 Mini-Ray 远程功能无缝集成

## 系统要求

- Python 3.7+
- Mini-Ray 框架
- Web 浏览器（Dashboard 客户端）

## 贡献

欢迎提交 Issue 和 Pull Request 来改进 Mini-Ray Dashboard！
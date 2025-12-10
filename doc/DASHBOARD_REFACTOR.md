# Mini-Ray Dashboard 重构文档

## 概述

此文档描述了对 Mini-Ray Dashboard 系统的重构，解决了原始问题："Dashboard 进程启动后，后续启动的训练任务无法被看到"。

## 重构方案

重构采用**双重策略**，结合了：

1. **事件通知系统** (方案2) - 实时通知任务状态变化
2. **持久化存储** (方案3) - 将任务信息持久化到共享存储

## 架构设计

### 1. 事件系统 (events.py)

- `EventBus`: 全局事件总线，负责发布和订阅事件
- `TaskEventType`: 任务事件类型枚举
- `TaskEvent`: 任务事件数据结构
- `SharedStorage`: 共享存储系统，负责持久化

### 2. 装饰器系统 (dashboard/tracking.py)

- `@track_training_job`: 训练任务跟踪装饰器
- `@track_inference_job`: 推理任务跟踪装饰器
- `@track_tuning_job`: 超参数调优跟踪装饰器

### 3. 持久化机制

- 所有任务状态变化都会生成事件
- 事件总线自动将事件信息写入持久化存储
- 使用临时目录存储任务信息 (e.g., `/tmp/miniray_dashboard/`)

## 解决原始问题的方法

### 问题：Dashboard 进程启动后，后续启动的训练任务无法被看到

**解决方案**：
1. 所有任务事件都通过 `EventBus` 发布
2. `EventBus` 自动将事件信息持久化到 `SharedStorage`
3. Dashboard API 从持久化存储获取任务信息
4. 无论 Dashboard 何时启动，都能看到完整的任务历史

### 工作流程

```
任务开始 → 事件发布 → 持久化存储 → Dashboard API → Web UI
```

## 使用方法

使用方式与之前相同，但功能更强大：

```python
from miniray import track_training_job

@track_training_job(name="My Training Job", description="模型训练任务")
def train_model(epochs):
    # 你的训练代码
    for epoch in range(epochs):
        # 训练逻辑
        pass
    return {"accuracy": 0.95}

result = train_model(epochs=10)  # 自动跟踪并持久化
```

## API 变更

Dashboard API 现在从持久化存储获取数据：
- `GET /api/tasks` - 获取所有任务
- `GET /api/training-jobs` - 获取训练任务
- `GET /api/stats` - 获取统计信息

## 数据结构

持久化数据包含完整的事件历史：

```json
{
  "task_id": "training_abc123",
  "name": "My Training Job",
  "status": "COMPLETED",
  "type": "training",
  "history": [
    {
      "event_type": "task_submitted",
      "timestamp": 1234567890.123,
      "timestamp_str": "2025-01-01T00:00:00.123456",
      "data": {"..."}
    }
  ],
  "updated_at": 1234567890.456,
  "updated_at_str": "2025-01-01T00:00:00.456789"
}
```

## 优势

1. **完全解决原始问题** - Dashboard 任意时间启动都能看到任务
2. **事件驱动** - 实时通知和更新
3. **持久化** - 任务信息不丢失
4. **向后兼容** - 现有代码无需修改
5. **可扩展** - 易于添加新的事件类型

## 测试

运行以下命令验证功能：

```bash
# 基础测试
python examples/test_refactored_dashboard.py

# 完整演示
python examples/demo_dashboard_decorator.py
```

## 总结

重构后的 Dashboard 系统实现了事件通知和持久化的双重保障，完全解决了原始问题，同时保持了对现有代码的向后兼容性。
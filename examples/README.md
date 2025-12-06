# Mini-Ray 示例

本目录包含 Mini-Ray 的使用示例，从简单到复杂逐步展示功能。

## 示例列表

### 01_object_store.py - 对象存储基础
演示如何使用 ObjectStore 进行对象的存储、获取和删除。

**运行方式：**
```bash
python examples/01_object_store.py
```

**学习要点：**
- 创建 ObjectStore
- 存储和获取字节数据
- 使用 pickle 序列化 Python 对象
- 检查对象是否存在
- 删除对象

### 02_scheduler.py - 调度器基础
演示如何使用 Scheduler 进行任务的提交、获取和 Worker 管理。

**运行方式：**
```bash
python examples/02_scheduler.py
```

**学习要点：**
- 创建 Scheduler
- 创建和提交任务
- 获取任务并执行
- Worker 注册和状态管理

### 03_simple_task.py - 简单任务执行
演示如何使用 CoreWorker 执行完整的任务流程。

**运行方式：**
```bash
python examples/03_simple_task.py
```

**学习要点：**
- 创建 CoreWorker
- 提交任务
- 执行任务
- 存储和获取结果

## 旧示例（已弃用）

- `01_phase1_object_store.py` - 旧的 Phase 1 示例，请使用 `01_object_store.py` 替代

## 下一步

查看 `tests/` 目录中的测试文件，了解更多高级用法。

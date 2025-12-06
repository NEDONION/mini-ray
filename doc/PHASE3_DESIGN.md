# Mini-Ray Phase 3 设计文档

> **版本**: v1.0
> **日期**: 2024-12-06
> **作者**: Mini-Ray Team
> **目标**: 将 Mini-Ray 从基础分布式框架升级为完整的 ML 工作流平台

---

## 📋 目录

1. [背景和动机](#背景和动机)
2. [Phase 3 目标](#phase-3-目标)
3. [方案对比](#方案对比)
4. [推荐方案：三合一架构](#推荐方案三合一架构)
5. [详细设计](#详细设计)
6. [前端 Dashboard 设计](#前端-dashboard-设计)
7. [实现计划](#实现计划)
8. [Demo 展示](#demo-展示)
9. [风险和挑战](#风险和挑战)

---

## 背景和动机

### Phase 1-2 完成的功能
✅ **Phase 1**: 对象存储 (ObjectStore)
- 共享内存对象存储
- Put/Get/Delete 操作
- Python 对象序列化

✅ **Phase 2**: 任务调度 (Scheduler + CoreWorker)
- 任务队列和调度
- Worker 管理
- 基础任务执行

### Phase 3 的必要性

当前 Mini-Ray 只是一个**任务执行引擎**，缺少：
1. **有状态计算** - 无法实现参数服务器、计数器等
2. **实际应用场景** - 缺少 ML 工程师关心的功能
3. **可观测性** - 无法监控任务执行状态
4. **任务编排** - 无法表达复杂的依赖关系

---

## Phase 3 目标

### 核心目标
1. **实现 Actor 模型** - Ray 的核心特性
2. **支持 ML 工作流** - 超参数调优、分布式训练
3. **增强可观测性** - Dashboard 监控面板
4. **提升易用性** - 装饰器语法、自动依赖解析

### 非目标（Phase 4+）
- ❌ 跨机器分布式（仍然单机多进程）
- ❌ GPU 调度
- ❌ 强化学习库
- ❌ 模型服务 (Serve)

---

## 方案对比

### 方案 A: 纯 Actor 模型
**优点**:
- 实现 Ray 的核心特性
- 架构完整性

**缺点**:
- 缺少实际应用场景
- 对 ML 工程师吸引力不足

**评分**: ⭐⭐⭐

---

### 方案 B: 纯 ML 应用（调优 + 训练）
**优点**:
- 实用价值高
- Demo 效果好

**缺点**:
- 缺少核心基础设施
- 功能受限

**评分**: ⭐⭐⭐⭐

---

### 方案 C: 三合一架构（推荐）
**包含**:
1. **Actor 模型** - 基础设施
2. **ML 工作流** - 应用层
3. **Dashboard** - 可视化

**优点**:
- ✅ 技术完整性
- ✅ 实用价值
- ✅ 展示效果
- ✅ 学习价值

**缺点**:
- 工作量较大（3-4 周）

**评分**: ⭐⭐⭐⭐⭐

---

## 推荐方案：三合一架构

```
┌─────────────────────────────────────────────────────────┐
│                    Mini-Ray Phase 3                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │         应用层 (ML Workflows)                    │   │
│  │  ┌──────────────┐  ┌──────────────┐            │   │
│  │  │ Hyperparameter│  │  Distributed │            │   │
│  │  │    Tuning     │  │   Training   │            │   │
│  │  └──────────────┘  └──────────────┘            │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │      基础设施层 (Infrastructure)                 │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │   │
│  │  │  Actor   │  │   Task   │  │  Object  │     │   │
│  │  │  Model   │  │   DAG    │  │  Store   │     │   │
│  │  └──────────┘  └──────────┘  └──────────┘     │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │        可视化层 (Dashboard)                      │   │
│  │  ┌──────────────────────────────────────────┐  │   │
│  │  │  Web UI (React + Flask)                   │  │   │
│  │  │  - 任务监控  - 资源图表  - 依赖可视化    │  │   │
│  │  └──────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 详细设计

### 1. Actor 模型

#### 1.1 核心概念

**Actor 定义**:
```python
@ray.remote
class Counter:
    def __init__(self, initial_value=0):
        self.value = initial_value

    def increment(self):
        self.value += 1
        return self.value

    def get_value(self):
        return self.value
```

**Actor 使用**:
```python
# 创建 Actor
counter = Counter.remote(initial_value=10)

# 调用方法（返回 ObjectRef）
ref1 = counter.increment.remote()
ref2 = counter.increment.remote()

# 获取结果
values = ray.get([ref1, ref2])  # [11, 12]
```

#### 1.2 架构设计

```
Actor 生命周期管理器 (ActorManager)
    │
    ├─ Actor 注册表 (ActorRegistry)
    │   ├─ actor_id -> ActorHandle 映射
    │   └─ ActorHandle: {class_def, state, worker_id}
    │
    ├─ Actor 调度器 (ActorScheduler)
    │   ├─ 决定 Actor 在哪个 Worker 上运行
    │   └─ Actor 方法调用路由
    │
    └─ Actor 状态管理 (ActorState)
        ├─ 序列化/反序列化 Actor 状态
        └─ Actor 方法队列（顺序执行保证）
```

#### 1.3 数据结构

**C++ 层**:
```cpp
// cpp/include/miniray/actor/actor.h
namespace miniray {
namespace actor {

struct ActorID {
    ObjectID id;  // 复用 ObjectID
};

struct ActorHandle {
    ActorID actor_id;
    std::string class_name;
    int worker_id;  // Actor 固定在哪个 Worker
};

struct ActorCall {
    ActorID actor_id;
    std::string method_name;
    std::vector<uint8_t> serialized_args;
    ObjectRef return_ref;
};

class ActorRegistry {
public:
    void RegisterActor(const ActorID& id, const ActorHandle& handle);
    ActorHandle GetActor(const ActorID& id);
    void UnregisterActor(const ActorID& id);

private:
    std::unordered_map<ActorID, ActorHandle> actors_;
    ProcessMutex mutex_;
};

}  // namespace actor
}  // namespace miniray
```

**Python 层**:
```python
# python/miniray/actor.py

class ActorClass:
    """被 @ray.remote 装饰的类的包装"""

    def __init__(self, cls):
        self._cls = cls
        self._methods = self._extract_methods(cls)

    def remote(self, *args, **kwargs):
        """创建 Actor 实例"""
        actor_id = generate_actor_id()

        # 序列化构造函数参数
        init_args = pickle.dumps((args, kwargs))

        # 提交 Actor 创建任务
        worker.create_actor(
            actor_id=actor_id,
            class_def=pickle.dumps(self._cls),
            init_args=init_args
        )

        return ActorHandle(actor_id, self._cls, self._methods)

class ActorHandle:
    """Actor 实例的句柄"""

    def __init__(self, actor_id, cls, methods):
        self._actor_id = actor_id
        self._cls = cls
        self._methods = methods

        # 动态创建方法代理
        for method_name in methods:
            setattr(self, method_name, self._make_method(method_name))

    def _make_method(self, method_name):
        """创建方法的 remote 版本"""
        class MethodProxy:
            def __init__(self, actor_id, method_name):
                self.actor_id = actor_id
                self.method_name = method_name

            def remote(self, *args, **kwargs):
                return ray._submit_actor_task(
                    self.actor_id,
                    self.method_name,
                    args,
                    kwargs
                )

        return MethodProxy(self._actor_id, method_name)
```

#### 1.4 执行流程

```
1. 用户代码: counter = Counter.remote(10)
   │
   ↓
2. Python: ActorClass.remote()
   │
   ↓
3. 创建 ActorID，序列化类定义和参数
   │
   ↓
4. 提交到 Scheduler（特殊的 Actor 创建任务）
   │
   ↓
5. Worker 获取任务，实例化 Actor 对象
   │
   ↓
6. 注册到 ActorRegistry
   │
   ↓
7. 返回 ActorHandle 给用户

---

1. 用户代码: ref = counter.increment.remote()
   │
   ↓
2. Python: MethodProxy.remote()
   │
   ↓
3. 创建 ActorCall 任务
   │
   ↓
4. 路由到 Actor 所在的 Worker
   │
   ↓
5. Worker 执行方法，返回结果
   │
   ↓
6. 结果存入 ObjectStore
   │
   ↓
7. 返回 ObjectRef
```

---

### 2. 任务依赖 (Task DAG)

#### 2.1 自动依赖识别

```python
@ray.remote
def load_data():
    return np.random.rand(1000, 10)

@ray.remote
def preprocess(data):
    return (data - data.mean()) / data.std()

@ray.remote
def train(data):
    model = LinearRegression()
    return model.fit(data[:, :-1], data[:, -1])

# 自动构建 DAG
data_ref = load_data.remote()           # 节点 1
clean_ref = preprocess.remote(data_ref) # 节点 2（依赖节点 1）
model_ref = train.remote(clean_ref)     # 节点 3（依赖节点 2）

# DAG:
#   load_data -> preprocess -> train
```

#### 2.2 依赖解析算法

```python
class TaskDAG:
    def __init__(self):
        self.tasks = {}  # task_id -> Task
        self.dependencies = {}  # task_id -> [dependency_ids]

    def add_task(self, task_id, task, dependencies):
        """添加任务到 DAG"""
        self.tasks[task_id] = task
        self.dependencies[task_id] = dependencies

    def topological_sort(self):
        """拓扑排序，返回执行顺序"""
        # Kahn 算法
        in_degree = {tid: 0 for tid in self.tasks}
        for deps in self.dependencies.values():
            for dep in deps:
                in_degree[dep] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            task_id = queue.pop(0)
            result.append(task_id)

            for tid, deps in self.dependencies.items():
                if task_id in deps:
                    in_degree[tid] -= 1
                    if in_degree[tid] == 0:
                        queue.append(tid)

        return result

    def is_ready(self, task_id):
        """检查任务的所有依赖是否已完成"""
        for dep_id in self.dependencies[task_id]:
            if not self.is_completed(dep_id):
                return False
        return True
```

---

### 3. ML 工作流

#### 3.1 超参数调优 (Hyperparameter Tuning)

**API 设计**:
```python
from miniray import tune

def train_function(config):
    """训练函数"""
    model = RandomForestClassifier(
        n_estimators=config['n_estimators'],
        max_depth=config['max_depth']
    )

    X, y = load_data()
    model.fit(X, y)
    score = model.score(X, y)

    return {'score': score, 'model': model}

# 运行调优
analysis = tune.run(
    train_function,
    config={
        'n_estimators': tune.grid_search([10, 50, 100]),
        'max_depth': tune.grid_search([3, 5, 10, None]),
    },
    metric='score',
    mode='max'
)

# 获取最佳配置
best_config = analysis.get_best_config()
best_model = analysis.get_best_trial().model
```

**实现架构**:
```
TuneController
    │
    ├─ SearchAlgorithm (搜索算法)
    │   ├─ GridSearch（网格搜索）
    │   ├─ RandomSearch（随机搜索）
    │   └─ BayesianOptimization（贝叶斯优化，可选）
    │
    ├─ TrialScheduler (试验调度)
    │   ├─ 并行运行多个试验
    │   └─ Early stopping（可选）
    │
    └─ ResultTracker (结果追踪)
        ├─ 记录每次试验结果
        ├─ 找出最佳配置
        └─ 生成分析报告
```

#### 3.2 分布式训练（简化版）

**数据并行训练**:
```python
@ray.remote
class DataParallelWorker:
    def __init__(self, model_class, rank):
        self.model = model_class()
        self.rank = rank

    def train_batch(self, data_batch, global_params):
        """训练一个批次"""
        self.model.set_params(global_params)
        loss = self.model.train_step(data_batch)
        gradients = self.model.get_gradients()
        return gradients, loss

def distributed_train(model_class, data, num_workers=4):
    # 创建 workers
    workers = [DataParallelWorker.remote(model_class, i)
               for i in range(num_workers)]

    # 数据分片
    shards = np.array_split(data, num_workers)

    # 训练循环
    params = init_params()
    for epoch in range(10):
        # 并行训练
        futures = [
            worker.train_batch.remote(shard, params)
            for worker, shard in zip(workers, shards)
        ]

        # 收集梯度
        results = ray.get(futures)
        gradients = [r[0] for r in results]

        # 平均梯度，更新参数
        avg_gradient = np.mean(gradients, axis=0)
        params = params - 0.01 * avg_gradient
```

---

### 4. 前端 Dashboard

#### 4.1 架构

```
┌─────────────────────────────────────┐
│        Frontend (React)              │
│  ┌────────────┐  ┌────────────┐    │
│  │  Dashboard │  │   Task     │    │
│  │   Panel    │  │   Graph    │    │
│  └────────────┘  └────────────┘    │
└─────────────────────────────────────┘
              ↓ HTTP/WebSocket
┌─────────────────────────────────────┐
│     Backend API (Flask)              │
│  ┌────────────────────────────────┐ │
│  │   /api/tasks                   │ │
│  │   /api/actors                  │ │
│  │   /api/metrics                 │ │
│  │   /ws/events (WebSocket)       │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│      Mini-Ray Core                   │
│  ┌────────────────────────────────┐ │
│  │  MetricsCollector              │ │
│  │  - Task events                 │ │
│  │  - Resource usage              │ │
│  │  - Actor status                │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

#### 4.2 功能模块

**1. 任务监控面板**
```jsx
// Dashboard 主页
function Dashboard() {
    const [tasks, setTasks] = useState([]);
    const [metrics, setMetrics] = useState({});

    useEffect(() => {
        // 轮询获取任务状态
        const interval = setInterval(async () => {
            const response = await fetch('/api/tasks');
            const data = await response.json();
            setTasks(data.tasks);
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    return (
        <div className="dashboard">
            <TaskTable tasks={tasks} />
            <MetricsChart metrics={metrics} />
            <ActorStatus actors={actors} />
        </div>
    );
}
```

**展示内容**:
- 任务列表（状态、耗时、Worker）
- 资源使用（CPU、内存、对象存储）
- Actor 状态（运行中、空闲、失败）
- 实时日志流

**2. 任务依赖图可视化**
```jsx
// 使用 ReactFlow 或 D3.js
import ReactFlow from 'react-flow-renderer';

function TaskDAGView({ tasks }) {
    const nodes = tasks.map(task => ({
        id: task.id,
        data: { label: task.name },
        position: calculatePosition(task)
    }));

    const edges = tasks.flatMap(task =>
        task.dependencies.map(dep => ({
            id: `${dep}-${task.id}`,
            source: dep,
            target: task.id
        }))
    );

    return <ReactFlow nodes={nodes} edges={edges} />;
}
```

**3. 性能指标图表**
```jsx
// 使用 Recharts
import { LineChart, Line, XAxis, YAxis } from 'recharts';

function MetricsChart({ metrics }) {
    return (
        <LineChart data={metrics.history}>
            <XAxis dataKey="timestamp" />
            <YAxis />
            <Line type="monotone" dataKey="tasks_per_second" stroke="#8884d8" />
            <Line type="monotone" dataKey="memory_usage" stroke="#82ca9d" />
        </LineChart>
    );
}
```

#### 4.3 后端 API

**Flask 应用**:
```python
# python/miniray/dashboard/app.py
from flask import Flask, jsonify
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/api/tasks')
def get_tasks():
    """获取所有任务状态"""
    tasks = ray.get_task_status()
    return jsonify({'tasks': tasks})

@app.route('/api/actors')
def get_actors():
    """获取所有 Actor 状态"""
    actors = ray.get_actor_status()
    return jsonify({'actors': actors})

@app.route('/api/metrics')
def get_metrics():
    """获取系统指标"""
    return jsonify({
        'tasks_per_second': ray.get_tasks_per_second(),
        'memory_usage': ray.get_memory_usage(),
        'worker_count': ray.get_worker_count()
    })

@socketio.on('connect')
def handle_connect():
    """WebSocket 连接"""
    print('Client connected')

def emit_task_event(event):
    """发送任务事件到前端"""
    socketio.emit('task_event', {
        'type': event.type,
        'task_id': event.task_id,
        'status': event.status
    })
```

---

## 实现计划

### Week 1: Actor 模型
| 任务 | 时间 | 负责人 |
|------|------|--------|
| Actor 数据结构设计 | 1d | |
| ActorRegistry 实现（C++） | 1d | |
| Actor 创建和调用（Python） | 2d | |
| Actor 测试用例 | 1d | |

**交付物**:
- ✅ 支持 `@ray.remote` 装饰类
- ✅ 支持 `Actor.remote()` 创建实例
- ✅ 支持 `actor.method.remote()` 调用
- ✅ 10+ 测试用例

---

### Week 2: 任务依赖 + 超参数调优
| 任务 | 时间 | 负责人 |
|------|------|--------|
| TaskDAG 实现 | 1d | |
| 自动依赖识别 | 1d | |
| Tune 框架基础 | 1d | |
| 网格搜索实现 | 1d | |
| 完整 ML Demo | 1d | |

**交付物**:
- ✅ 自动识别任务依赖
- ✅ `tune.run()` API
- ✅ GridSearch 算法
- ✅ MNIST/Iris 分类 Demo

---

### Week 3: Dashboard
| 任务 | 时间 | 负责人 |
|------|------|--------|
| MetricsCollector（C++） | 1d | |
| Flask API 实现 | 1d | |
| React 前端搭建 | 2d | |
| 集成测试 | 1d | |

**交付物**:
- ✅ Web UI 监控面板
- ✅ 实时任务状态
- ✅ 依赖图可视化
- ✅ 性能指标图表

---

### Week 4: 集成和优化
| 任务 | 时间 | 负责人 |
|------|------|--------|
| 端到端集成测试 | 2d | |
| 性能优化 | 1d | |
| 文档和示例 | 1d | |
| Demo 准备 | 1d | |

---

## Demo 展示

### Demo 1: 分布式超参数调优

**场景**: 为 MNIST 手写数字识别找最佳超参数

```python
from miniray import tune
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

# 1. 定义训练函数
def train_mnist(config):
    X, y = load_digits(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    model = RandomForestClassifier(
        n_estimators=config['n_estimators'],
        max_depth=config['max_depth'],
        min_samples_split=config['min_samples_split']
    )

    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)

    return {
        'accuracy': score,
        'model': model
    }

# 2. 运行超参数搜索
analysis = tune.run(
    train_mnist,
    config={
        'n_estimators': tune.grid_search([10, 50, 100, 200]),
        'max_depth': tune.grid_search([3, 5, 10, None]),
        'min_samples_split': tune.grid_search([2, 5, 10]),
    },
    metric='accuracy',
    mode='max',
    num_samples=1,  # 每个配置运行 1 次
)

# 3. 查看结果
print(f"搜索了 {len(analysis.trials)} 个配置")
print(f"最佳准确率: {analysis.best_trial.metrics['accuracy']:.4f}")
print(f"最佳配置: {analysis.best_config}")

# 4. 在 Dashboard 中查看
# - 打开 http://localhost:8265
# - 看到 48 个任务并行执行
# - 实时更新每个配置的准确率
# - 可视化参数-性能关系
```

**预期效果**:
- 单机顺序执行：~10 分钟
- Mini-Ray 并行（4 workers）：~3 分钟
- **加速比**: 3-4x

---

### Demo 2: Actor 实现参数服务器

**场景**: 分布式训练中的参数同步

```python
import numpy as np
import ray

# 1. 定义参数服务器 Actor
@ray.remote
class ParameterServer:
    def __init__(self, dim):
        self.params = np.zeros(dim)
        self.version = 0

    def get_params(self):
        return self.params, self.version

    def update_params(self, gradients):
        self.params -= 0.01 * gradients
        self.version += 1
        return self.version

# 2. 定义 Worker Actor
@ray.remote
class TrainingWorker:
    def __init__(self, worker_id, data_shard):
        self.worker_id = worker_id
        self.data = data_shard

    def compute_gradients(self, params):
        # 模拟计算梯度
        gradients = np.random.randn(*params.shape)
        return gradients

# 3. 创建 Actors
ps = ParameterServer.remote(dim=100)
workers = [TrainingWorker.remote(i, data_shards[i])
           for i in range(4)]

# 4. 训练循环
for epoch in range(10):
    # 获取当前参数
    params, version = ray.get(ps.get_params.remote())

    # 并行计算梯度
    gradient_refs = [
        worker.compute_gradients.remote(params)
        for worker in workers
    ]
    gradients = ray.get(gradient_refs)

    # 平均梯度并更新
    avg_gradient = np.mean(gradients, axis=0)
    new_version = ray.get(ps.update_params.remote(avg_gradient))

    print(f"Epoch {epoch}, Version {new_version}")
```

---

### Demo 3: Dashboard 实时监控

**启动步骤**:
```bash
# 1. 启动 Mini-Ray
python -m miniray start --head

# 2. 启动 Dashboard
python -m miniray.dashboard

# 3. 打开浏览器
open http://localhost:8265
```

**展示内容**:
1. **任务面板** - 显示所有运行中的任务
2. **Actor 面板** - 显示所有 Actor 及其状态
3. **依赖图** - 可视化任务依赖关系
4. **性能图表** - CPU、内存、吞吐量实时曲线
5. **日志流** - 实时显示系统日志

**截图示意**:
```
┌────────────────────────────────────────────────────────┐
│  Mini-Ray Dashboard                    ⚡ Connected    │
├────────────────────────────────────────────────────────┤
│  Tasks (Running: 12 | Completed: 45 | Failed: 0)      │
│  ┌──────────┬──────────┬─────────┬──────────────────┐ │
│  │ Task ID  │  Status  │ Worker  │    Runtime       │ │
│  ├──────────┼──────────┼─────────┼──────────────────┤ │
│  │ task-001 │ RUNNING  │   W-1   │      2.3s        │ │
│  │ task-002 │ RUNNING  │   W-2   │      1.8s        │ │
│  │ task-003 │ PENDING  │    -    │       -          │ │
│  └──────────┴──────────┴─────────┴──────────────────┘ │
│                                                         │
│  Task Dependency Graph                                 │
│  ┌─────────────────────────────────────────────────┐  │
│  │     [load_data]                                  │  │
│  │          │                                       │  │
│  │          ↓                                       │  │
│  │   [preprocess] → [train] → [evaluate]           │  │
│  └─────────────────────────────────────────────────┘  │
│                                                         │
│  System Metrics                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │   CPU: ████████░░ 80%                            │  │
│  │   Mem: ██████░░░░ 60%                            │  │
│  │   TPS: 45 tasks/sec                              │  │
│  └─────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 技术栈

### 后端
- **Core**: C++ 17 (现有代码)
- **Bindings**: pybind11
- **API Server**: Flask + Flask-SocketIO
- **Metrics**: 自定义 MetricsCollector

### 前端
- **框架**: React 18
- **UI 库**: Ant Design / Material-UI
- **图表**: Recharts / ECharts
- **DAG 可视化**: ReactFlow / Cytoscape.js
- **状态管理**: Redux Toolkit (可选)

### 开发工具
- **构建**: Vite (React) + CMake (C++)
- **测试**: pytest + Jest
- **文档**: Sphinx + Storybook

---

## 风险和挑战

### 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Actor 状态序列化复杂 | 高 | 限制 Actor 状态只能是可 pickle 对象 |
| 前端开发时间不足 | 中 | 使用现成 UI 库，MVP 优先 |
| 性能瓶颈 | 中 | 早期性能测试，优化关键路径 |
| DAG 环检测 | 低 | 使用成熟的拓扑排序算法 |

### 项目风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 开发时间超期 | 高 | 分阶段交付，核心功能优先 |
| 功能过于复杂 | 中 | 坚持 MVP 原则，避免过度设计 |
| 测试覆盖不足 | 中 | TDD 开发，每个功能先写测试 |

---

## 成功标准

### 功能完整性
- ✅ 支持 Actor 模型（创建、调用、状态管理）
- ✅ 支持任务依赖自动识别
- ✅ 支持超参数网格搜索
- ✅ Dashboard 可查看任务和 Actor 状态

### 性能指标
- ✅ 超参数调优加速比 > 3x（4 workers）
- ✅ Actor 方法调用延迟 < 10ms
- ✅ Dashboard 刷新率 > 1 FPS

### 代码质量
- ✅ 测试覆盖率 > 80%
- ✅ 所有公有 API 有文档
- ✅ 至少 3 个完整 Demo

---

## 后续计划 (Phase 4+)

### 短期（1-2 月）
- 🔄 容错和重试机制
- 🔄 对象生命周期管理（引用计数、GC）
- 🔄 更多调优算法（贝叶斯优化、HyperBand）

### 中期（3-6 月）
- 🔄 跨机器分布式（网络通信）
- 🔄 GPU 资源管理
- 🔄 Placement Groups

### 长期（6+ 月）
- 🔄 Ray Train 完整实现
- 🔄 Ray Serve（模型服务）
- 🔄 云平台集成

---

## 参考资料

- [Ray Architecture Whitepaper](https://arxiv.org/abs/1712.05889)
- [Ray Documentation](https://docs.ray.io/)
- [Actor Model - Wikipedia](https://en.wikipedia.org/wiki/Actor_model)
- [React + Flask Full Stack Tutorial](https://blog.miguelgrinberg.com/post/how-to-create-a-react--flask-project)

---

## 附录

### A. API 设计汇总

```python
# Actor API
@ray.remote
class MyActor:
    def __init__(self):
        pass

    def method(self):
        pass

actor = MyActor.remote()
ref = actor.method.remote()
result = ray.get(ref)

# Tune API
tune.run(
    train_function,
    config={
        'param': tune.grid_search([1, 2, 3])
    }
)

# Dashboard API
GET  /api/tasks
GET  /api/actors
GET  /api/metrics
WS   /ws/events
```

### B. 目录结构

```
mini-ray/
├── cpp/
│   ├── include/miniray/
│   │   ├── actor/
│   │   │   ├── actor.h
│   │   │   └── actor_registry.h
│   │   └── ...
│   └── src/actor/
│       ├── actor.cpp
│       └── actor_registry.cpp
├── python/miniray/
│   ├── actor.py
│   ├── tune/
│   │   ├── __init__.py
│   │   ├── tune.py
│   │   └── search.py
│   └── dashboard/
│       ├── app.py
│       └── frontend/
│           ├── src/
│           └── package.json
└── examples/
    ├── 04_actor_counter.py
    ├── 05_hyperparameter_tuning.py
    └── 06_parameter_server.py
```

---

**文档版本**: v1.0
**最后更新**: 2024-12-06
**状态**: ✅ Ready for Review

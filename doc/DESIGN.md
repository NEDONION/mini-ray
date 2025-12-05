# Mini-Ray 设计文档

> 一个采用 **Python/C++ 异构架构** 的简化版 Ray 分布式计算框架
> 目标：通过模拟真实 Ray 的分层设计，深入理解分布式系统的核心原理

---

## 🎯 项目目标

通过实现一个 **高度还原** Ray 架构的 mini 版本，理解以下核心概念：

1. **远程函数执行**（Task Execution）
2. **对象存储**（Object Store）- **C++ 实现的共享内存存储**
3. **任务调度**（Scheduler）- **C++ 实现的高性能调度器**
4. **Python/C++ 互操作**（Language Bindings）
5. **CoreWorker 架构**（每个进程的核心组件）
6. **有状态对象**（Actor Model）

### 🌟 为什么要 Python/C++ 异构？

参考真实 Ray 的设计哲学：

| 层次 | 语言 | 职责 | 原因 |
|------|------|------|------|
| **API 层** | Python | 用户接口、装饰器、序列化 | 易用性、灵活性 |
| **绑定层** | pybind11 | Python ↔ C++ 类型转换 | 跨语言桥梁 |
| **核心层** | C++ | 调度、存储、通信、资源管理 | 性能、并发控制 |

**学习收益**：
- 理解为什么 Ray 要用 C++ 实现核心组件
- 掌握 Python/C++ 混合编程的最佳实践
- 体验真实生产级框架的工程架构

---

## 🏗️ 整体架构（Python/C++ 分层）

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户代码层 (Python)                           │
│       @miniray.remote  |  miniray.get()  |  miniray.init()      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                  Python 封装层 (Python)                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │ api.py           │  │ actor.py         │  │ worker.py     │ │
│  │ - init()         │  │ - ActorClass     │  │ - Worker 管理 │ │
│  │ - get()          │  │ - ActorHandle    │  │ - 序列化      │ │
│  │ - remote()       │  │                  │  │               │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│               Python/C++ 绑定层 (pybind11)                       │
│                        _miniray_core.so                          │
│  - ObjectRef (C++ → Python)                                      │
│  - CoreWorker (C++ → Python)                                     │
│  - ObjectStore API 绑定                                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    C++ 核心层 (C++)                              │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ CoreWorker     │  │ ObjectStore    │  │ Scheduler        │  │
│  │ (core_worker/) │  │ (object_store/)│  │ (scheduler/)     │  │
│  │                │  │                │  │                  │  │
│  │ - SubmitTask() │  │ - Put()        │  │ - ScheduleTask() │  │
│  │ - GetObject()  │  │ - Get()        │  │ - AssignWorker() │  │
│  │ - CreateActor()│  │ - Delete()     │  │ - TaskQueue      │  │
│  │                │  │ - 共享内存管理  │  │                  │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  Common 工具库 (common/)                   │ │
│  │  - Task 定义                                               │ │
│  │  - ObjectRef 定义                                          │ │
│  │  - 序列化工具                                               │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│               底层通信（跨进程通信）                              │
│  - 共享内存 (boost::interprocess 或 POSIX shm)                  │
│  - 本地 Socket/Pipe（控制信息）                                  │
│  - 多进程（Python multiprocessing）                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 核心组件详解

### 1. CoreWorker（核心工作组件）**[C++]**

> 参考：Ray 的 `cpp/src/ray/core_worker/core_worker.h`

**职责**：
- 每个 Worker 进程都有一个 CoreWorker 实例
- 任务提交和执行的核心逻辑
- 与 ObjectStore、Scheduler 交互

**C++ 实现**（`cpp/src/core_worker/core_worker.h`）：
```cpp
class CoreWorker {
public:
    // 提交任务
    ObjectRef SubmitTask(const TaskSpec& task_spec);

    // 获取对象
    std::vector<std::shared_ptr<Buffer>> GetObjects(
        const std::vector<ObjectRef>& object_refs);

    // 存储对象
    ObjectRef Put(const std::shared_ptr<Buffer>& data);

    // 创建 Actor
    ActorHandle CreateActor(const ActorCreationSpec& actor_spec);

private:
    std::unique_ptr<ObjectStore> object_store_;
    std::unique_ptr<TaskSubmitter> task_submitter_;
};
```

**Python 绑定**（使用 pybind11）：
```python
# Python 调用
core_worker.submit_task(task_spec)
core_worker.get_objects([ref1, ref2])
```

---

### 2. ObjectStore（对象存储）**[C++]**

> 参考：Ray 的 Plasma 对象存储（简化版）

**职责**：
- 共享内存管理
- 零拷贝对象传输（进程间）
- 对象生命周期管理

**C++ 实现**（`cpp/src/object_store/object_store.h`）：
```cpp
class ObjectStore {
public:
    // 存储对象到共享内存
    ObjectRef Put(const std::shared_ptr<Buffer>& data);

    // 从共享内存获取对象
    std::shared_ptr<Buffer> Get(const ObjectRef& object_ref);

    // 删除对象
    void Delete(const ObjectRef& object_ref);

    // 检查对象是否存在
    bool Contains(const ObjectRef& object_ref);

private:
    // 共享内存映射：ObjectID -> 共享内存地址
    std::unordered_map<ObjectID, void*> objects_;

    // 使用 boost::interprocess 或 POSIX shm_open
    boost::interprocess::managed_shared_memory segment_;
};
```

**为什么用 C++ 实现？**
- 共享内存管理需要精确控制内存布局
- 避免 Python GIL 限制
- 支持零拷贝（进程间直接访问内存）

---

### 3. Scheduler（任务调度器）**[C++]**

> 参考：Ray 的 Raylet 调度器（简化版）

**职责**：
- 接收任务提交
- 分配任务到 Worker
- 管理任务队列和 Worker 池

**C++ 实现**（`cpp/src/scheduler/scheduler.h`）：
```cpp
class Scheduler {
public:
    // 提交任务
    void SubmitTask(const Task& task);

    // 调度循环（在独立线程中运行）
    void ScheduleLoop();

    // 注册 Worker
    void RegisterWorker(WorkerID worker_id);

    // Worker 请求任务
    std::optional<Task> GetTask(WorkerID worker_id);

private:
    // 任务队列（按优先级）
    std::queue<Task> task_queue_;

    // Worker 池
    std::vector<WorkerID> available_workers_;

    // 线程安全保护
    std::mutex queue_mutex_;
    std::condition_variable queue_cv_;
};
```

**调度策略**：
- Phase 1: 简单的 FIFO + Round Robin
- Phase 2: 可扩展为数据本地性调度

---

### 4. Task（任务定义）**[C++]**

**C++ 实现**（`cpp/src/common/task.h`）：
```cpp
struct TaskSpec {
    TaskID task_id;
    FunctionID function_id;
    std::vector<ObjectRef> args;  // 参数可能是 ObjectRef
    std::map<std::string, ObjectRef> kwargs;
};

struct Task {
    TaskSpec task_spec;
    ObjectRef return_ref;  // 返回值的 ObjectRef

    // 序列化的函数体（Python 函数通过 pickle 序列化）
    std::vector<uint8_t> serialized_function;
};
```

---

### 5. ObjectRef（对象引用）**[C++]**

**C++ 实现**（`cpp/src/common/object_ref.h`）：
```cpp
class ObjectRef {
public:
    ObjectRef() : object_id_(ObjectID::FromRandom()) {}
    explicit ObjectRef(const ObjectID& object_id) : object_id_(object_id) {}

    const ObjectID& GetObjectID() const { return object_id_; }

    // Python 绑定需要
    std::string ToString() const;

private:
    ObjectID object_id_;  // 128-bit UUID
};
```

**Python 绑定**（pybind11）：
```cpp
py::class_<ObjectRef>(m, "ObjectRef")
    .def(py::init<>())
    .def("__repr__", &ObjectRef::ToString);
```

---

### 6. Python 封装层

#### 6.1 API 层（`api.py`）**[Python]**

```python
# 全局 CoreWorker 实例
_global_core_worker = None

def init(num_workers=4):
    """初始化 Mini-Ray"""
    global _global_core_worker
    # 创建 C++ CoreWorker
    _global_core_worker = _miniray_core.CoreWorker(num_workers)
    # 启动 Scheduler 和 Workers

def get(object_refs):
    """获取对象"""
    if isinstance(object_refs, list):
        return _global_core_worker.get_objects(object_refs)
    else:
        return _global_core_worker.get_objects([object_refs])[0]

def remote(func_or_class):
    """装饰器"""
    if isinstance(func_or_class, type):
        return ActorClass(func_or_class)
    else:
        return RemoteFunction(func_or_class)
```

#### 6.2 RemoteFunction（`api.py`）**[Python]**

```python
class RemoteFunction:
    def __init__(self, func):
        self._func = func
        self._func_id = _register_function(func)

    def remote(self, *args, **kwargs):
        # 序列化函数和参数
        serialized_func = pickle.dumps(self._func)

        # 创建 TaskSpec（C++ 对象）
        task_spec = _miniray_core.TaskSpec(
            function_id=self._func_id,
            serialized_function=serialized_func,
            args=args,
            kwargs=kwargs
        )

        # 提交到 C++ CoreWorker
        return _global_core_worker.submit_task(task_spec)
```

#### 6.3 Actor（`actor.py`）**[Python]**

```python
class ActorClass:
    def __init__(self, cls):
        self._cls = cls

    def remote(self, *args, **kwargs):
        # 创建 Actor（在 C++ 中分配专属 Worker）
        actor_handle = _global_core_worker.create_actor(
            cls=self._cls,
            args=args,
            kwargs=kwargs
        )
        return ActorHandle(actor_handle)

class ActorHandle:
    def __init__(self, cpp_handle):
        self._cpp_handle = cpp_handle

    def __getattr__(self, name):
        # 动态生成方法调用
        return ActorMethod(self._cpp_handle, name)
```

---

### 7. Worker 进程管理 **[Python + C++]**

**Python 侧**（`worker.py`）：
```python
def worker_main(worker_id, scheduler_address):
    """Worker 进程主函数"""
    # 创建 C++ CoreWorker
    core_worker = _miniray_core.CoreWorker(worker_id)

    while True:
        # 从 Scheduler 获取任务（C++ 调用）
        task = core_worker.get_next_task()
        if task is None:
            break

        # 反序列化函数
        func = pickle.loads(task.serialized_function)

        # 执行
        result = func(*task.args, **task.kwargs)

        # 存储结果到 ObjectStore（C++ 调用）
        core_worker.put(task.return_ref, result)
```

**C++ 侧**：
- `CoreWorker::GetNextTask()` - 从 Scheduler 拉取任务
- `CoreWorker::Put()` - 存储结果到 ObjectStore

---

## 📝 核心 API 设计

### 初始化

```python
import miniray

# 启动 Mini-Ray
miniray.init(num_workers=4)
```

### 远程函数

```python
@miniray.remote
def add(a, b):
    return a + b

# 提交任务，返回 ObjectRef
ref = add.remote(1, 2)

# 获取结果
result = miniray.get(ref)
print(result)  # 3
```

### 批量操作

```python
# 并行提交多个任务
refs = [add.remote(i, i) for i in range(10)]

# 批量获取结果
results = miniray.get(refs)
print(results)  # [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
```

### Actor（有状态对象）

```python
@miniray.remote
class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1
        return self.value

# 创建 Actor
counter = Counter.remote()

# 调用方法
result = miniray.get(counter.increment.remote())
print(result)  # 1
```

---

## 🚀 实现路线图（分阶段）

### Phase 1: C++ 核心基础设施（第 1-2 周）

**目标**：搭建 C++ 核心层和 Python 绑定

1. **C++ 项目结构**
   - [ ] 建立 CMake 构建系统
   - [ ] 配置 pybind11
   - [ ] 目录结构：`cpp/src/{common,core_worker,object_store,scheduler}`

2. **基础数据结构（C++）**
   - [ ] `ObjectID`、`TaskID`、`WorkerID`（UUID 生成）
   - [ ] `ObjectRef` 类
   - [ ] `Task` 和 `TaskSpec` 结构

3. **ObjectStore 实现（C++）**
   - [ ] 共享内存管理（使用 `boost::interprocess` 或 POSIX shm）
   - [ ] `Put()` / `Get()` / `Delete()` 接口
   - [ ] 简单的引用计数

4. **Python 绑定**
   - [ ] pybind11 绑定 `ObjectRef`
   - [ ] pybind11 绑定 `ObjectStore`
   - [ ] 测试 Python ↔ C++ 数据传输

**验收标准**：
```python
import _miniray_core
store = _miniray_core.ObjectStore()
ref = store.put(b"hello")
data = store.get(ref)
assert data == b"hello"
```

---

### Phase 2: 任务调度和执行（第 3-4 周）

1. **Scheduler 实现（C++）**
   - [ ] 任务队列（`std::queue`）
   - [ ] Worker 注册和管理
   - [ ] 简单的 FIFO 调度
   - [ ] 线程安全（`std::mutex`）

2. **CoreWorker 实现（C++）**
   - [ ] `SubmitTask()` 接口
   - [ ] `GetNextTask()` 接口（Worker 侧）
   - [ ] 与 Scheduler 通信

3. **Worker 进程（Python）**
   - [ ] `worker.py` - Worker 主循环
   - [ ] 使用 `multiprocessing.Process` 启动
   - [ ] 反序列化和执行 Python 函数

4. **端到端任务执行**
   - [ ] 主进程提交任务 → Scheduler → Worker 执行 → ObjectStore 存储结果

**验收标准**：
```python
import miniray
miniray.init(num_workers=2)

@miniray.remote
def add(a, b):
    return a + b

ref = add.remote(1, 2)
result = miniray.get(ref)
assert result == 3
```

---

### Phase 3: Python API 层（第 5 周）

1. **核心 API（Python）**
   - [ ] `miniray.init()` - 启动系统
   - [ ] `miniray.get()` - 获取对象
   - [ ] `miniray.shutdown()` - 关闭系统

2. **装饰器实现（Python）**
   - [ ] `@miniray.remote` 装饰器
   - [ ] `RemoteFunction` 类
   - [ ] 函数序列化（pickle）

3. **批量操作**
   - [ ] `miniray.get([ref1, ref2, ...])` 批量获取
   - [ ] `miniray.wait([ref1, ref2])` 等待完成

**验收标准**：
```python
# 批量任务
refs = [add.remote(i, i) for i in range(100)]
results = miniray.get(refs)
assert sum(results) == sum(i*2 for i in range(100))
```

---

### Phase 4: Actor 支持（第 6-7 周）

1. **Actor 调度（C++）**
   - [ ] Actor 专属 Worker 分配
   - [ ] Actor 方法调用队列（保证顺序执行）

2. **Actor API（Python）**
   - [ ] `ActorClass` 实现
   - [ ] `ActorHandle` 实现
   - [ ] `actor.method.remote()` 语法

**验收标准**：
```python
@miniray.remote
class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1
        return self.value

counter = Counter.remote()
refs = [counter.increment.remote() for _ in range(10)]
results = miniray.get(refs)
assert results == list(range(1, 11))
```

---

### Phase 5: 高级特性（可选，第 8+ 周）

1. **错误处理**
   - [ ] 任务失败检测
   - [ ] 异常传播到主进程

2. **资源管理**
   - [ ] CPU/GPU 资源声明
   - [ ] 基于资源的调度

3. **监控和调试**
   - [ ] 任务执行时间统计
   - [ ] Worker 状态查询

4. **性能优化**
   - [ ] 对象引用计数和垃圾回收
   - [ ] 零拷贝优化

---

## 💡 关键技术点

### 1. Python/C++ 绑定（pybind11）

**为什么选择 pybind11？**
- 轻量级（header-only）
- 与 C++11/14/17 完美集成
- Ray 也使用 pybind11（部分模块）

**基本用法**：

```cpp
// cpp/src/python_bindings.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>  // 自动转换 std::vector 等

namespace py = pybind11;

PYBIND11_MODULE(_miniray_core, m) {
    // 绑定 ObjectRef
    py::class_<ObjectRef>(m, "ObjectRef")
        .def(py::init<>())
        .def("__repr__", &ObjectRef::ToString);

    // 绑定 ObjectStore
    py::class_<ObjectStore>(m, "ObjectStore")
        .def(py::init<>())
        .def("put", &ObjectStore::Put)
        .def("get", &ObjectStore::Get);

    // 绑定 CoreWorker
    py::class_<CoreWorker>(m, "CoreWorker")
        .def(py::init<int>())
        .def("submit_task", &CoreWorker::SubmitTask)
        .def("get_objects", &CoreWorker::GetObjects);
}
```

**Python 调用**：
```python
import _miniray_core

# 创建对象
store = _miniray_core.ObjectStore()
worker = _miniray_core.CoreWorker(num_workers=4)
```

---

### 2. 共享内存实现（C++）

**方案选择**：
- **Option 1**: Boost.Interprocess（推荐，跨平台）
- **Option 2**: POSIX `shm_open` + `mmap`（Unix only）

**Boost.Interprocess 示例**：

```cpp
#include <boost/interprocess/managed_shared_memory.hpp>

class ObjectStore {
private:
    boost::interprocess::managed_shared_memory segment_;

public:
    ObjectStore()
        : segment_(boost::interprocess::create_only,
                   "MiniRayObjectStore",
                   1024 * 1024 * 1024) {}  // 1GB

    ObjectRef Put(const py::bytes& data) {
        // 分配共享内存
        void* ptr = segment_.allocate(data.size());
        std::memcpy(ptr, data.ptr(), data.size());

        // 创建 ObjectRef
        ObjectRef ref;
        objects_[ref.GetObjectID()] = {ptr, data.size()};
        return ref;
    }

    py::bytes Get(const ObjectRef& ref) {
        auto it = objects_.find(ref.GetObjectID());
        if (it == objects_.end()) {
            throw std::runtime_error("Object not found");
        }

        // 从共享内存读取
        return py::bytes(static_cast<char*>(it->second.ptr),
                         it->second.size);
    }
};
```

**为什么不用 Python Manager().dict()？**
- Manager 有性能开销（每次访问都是 IPC）
- 无法实现零拷贝
- 无法精确控制内存布局

---

### 3. 序列化策略

**Python 函数序列化**（Python 侧）：
```python
import pickle
import cloudpickle  # 更强大，支持 lambda

def serialize_function(func):
    """序列化 Python 函数"""
    try:
        return cloudpickle.dumps(func)
    except Exception:
        return pickle.dumps(func)
```

**C++ 端处理**：
```cpp
struct Task {
    // 序列化的函数（不反序列化，只传输）
    std::vector<uint8_t> serialized_function;

    // 序列化的参数
    std::vector<uint8_t> serialized_args;
};
```

**注意**：C++ 只负责存储和传输，不解析 Python 对象

---

### 4. 跨进程通信架构

**通信模型**：
```
主进程 (Python)
    ↓ [提交任务]
CoreWorker (C++)
    ↓ [写入任务队列]
Scheduler (C++)
    ↓ [分配任务]
Worker 进程 (Python)
    ↓ [执行任务]
CoreWorker (C++)
    ↓ [存储结果]
ObjectStore (C++ 共享内存)
```

**通信方式**：
1. **任务提交**：主进程 → Scheduler（通过 CoreWorker）
   - 使用 POSIX 消息队列或 Unix Domain Socket
2. **任务获取**：Scheduler → Worker
   - Worker 主动拉取（Pull 模式）
3. **对象存储**：所有进程 → ObjectStore
   - 共享内存（零拷贝）

---

### 5. 多线程安全（C++）

**Scheduler 线程安全**：
```cpp
class Scheduler {
private:
    std::queue<Task> task_queue_;
    std::mutex queue_mutex_;
    std::condition_variable queue_cv_;

public:
    void SubmitTask(const Task& task) {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        task_queue_.push(task);
        queue_cv_.notify_one();  // 唤醒等待的 Worker
    }

    std::optional<Task> GetTask() {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        queue_cv_.wait(lock, [this] {
            return !task_queue_.empty();
        });

        Task task = task_queue_.front();
        task_queue_.pop();
        return task;
    }
};
```

---

### 6. CMake 构建系统

**项目结构**：
```
mini-ray/
├── CMakeLists.txt          # 根 CMake
├── cpp/
│   ├── CMakeLists.txt      # C++ 构建
│   ├── src/
│   │   ├── common/
│   │   ├── core_worker/
│   │   ├── object_store/
│   │   ├── scheduler/
│   │   └── python_bindings.cpp
│   └── include/
├── setup.py                # Python 包配置
└── miniray/
    └── __init__.py
```

**根 CMakeLists.txt**：
```cmake
cmake_minimum_required(VERSION 3.15)
project(miniray)

set(CMAKE_CXX_STANDARD 17)

# 查找 pybind11
find_package(pybind11 REQUIRED)

# 查找 Boost
find_package(Boost REQUIRED COMPONENTS system)

# 添加子目录
add_subdirectory(cpp)
```

**cpp/CMakeLists.txt**：
```cmake
# 编译 C++ 库
add_library(miniray_core SHARED
    src/object_store/object_store.cpp
    src/scheduler/scheduler.cpp
    src/core_worker/core_worker.cpp
    src/python_bindings.cpp
)

target_link_libraries(miniray_core
    PRIVATE pybind11::module
    PRIVATE Boost::system
)

# 设置输出名称
set_target_properties(miniray_core PROPERTIES
    PREFIX ""  # 去掉 lib 前缀
    OUTPUT_NAME "_miniray_core"
)
```

**setup.py**（集成 CMake）：
```python
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import subprocess

class CMakeBuild(build_ext):
    def run(self):
        subprocess.check_call(['cmake', '-B', 'build', '-S', '.'])
        subprocess.check_call(['cmake', '--build', 'build'])

setup(
    name='miniray',
    ext_modules=[Extension('_miniray_core', sources=[])],
    cmdclass={'build_ext': CMakeBuild},
)
```

---

## 🎓 学习收益

通过实现这个 **Python/C++ 异构** 的 Mini-Ray，你将深入理解：

### 1. 分布式系统架构

- **主从模式**（Master-Worker）
- **任务队列和调度算法**
- **对象存储和引用计数**
- **进程间通信（IPC）模式**

### 2. Python/C++ 混合编程

- **pybind11 的使用**
  - 类型转换（`py::bytes`, `py::list`）
  - 异常处理（C++ → Python）
  - GIL 管理
- **构建系统**（CMake + setuptools）
- **调试技巧**（GDB + pdb 联合调试）

### 3. 系统编程技术

- **共享内存管理**
  - Boost.Interprocess 或 POSIX shm
  - 内存对齐和布局
  - 零拷贝优化
- **多线程和同步**
  - `std::mutex`, `std::condition_variable`
  - 生产者-消费者模式
- **进程管理**
  - `fork()` vs `multiprocessing.Process`
  - 进程生命周期管理

### 4. 真实 Ray 的核心设计

- **为什么 Ray 用 C++ 实现核心？**
  - 性能（避免 GIL）
  - 精确的内存控制
  - 更好的并发支持
- **CoreWorker 架构**
  - 每个 Worker 进程的核心组件
  - 统一的任务提交和对象管理接口
- **Plasma 对象存储的简化实现**
  - 共享内存 vs 网络传输
  - 对象生命周期管理

### 5. 软件工程实践

- **模块化设计**（分层架构）
- **接口设计**（API vs Implementation）
- **测试驱动开发**（每个 Phase 都有验收标准）
- **渐进式开发**（从简单到复杂）

---

## 🔍 与真实 Ray 的对比

| 特性 | Mini-Ray（本项目） | 真实 Ray |
|------|-------------------|----------|
| **架构** | Python API + C++ 核心 ✅ | Python API + Cython + C++ 核心 |
| **对象存储** | C++ 共享内存（简化版 Plasma）✅ | Plasma（Apache Arrow）|
| **调度器** | C++ FIFO 调度器 ✅ | Raylet（分布式调度）|
| **网络通信** | 单机（共享内存 + Pipe）| gRPC（分布式）|
| **GCS** | 无（简化） | 全局控制存储（Redis/自研）|
| **容错** | 无（Phase 5 可选）| 自动重试、容错 |
| **资源管理** | 简单 Worker 池 | CPU/GPU/内存 调度 |
| **语言支持** | Python only | Python, Java, C++ |
| **性能** | 教学用途 | 生产级（百万 QPS）|

**核心思想一致**：
- ✅ 任务抽象（Task）
- ✅ 对象引用（ObjectRef）
- ✅ CoreWorker 架构
- ✅ Python/C++ 分层
- ✅ Actor 模型

---

## 📚 进阶扩展方向

完成基础实现后，可以尝试这些挑战：

### 1. 性能优化

- [ ] **对象引用计数和垃圾回收**
  - 实现引用计数机制
  - 自动释放不再使用的对象
- [ ] **零拷贝优化**
  - 使用 `mmap` 直接映射共享内存
  - 避免数据拷贝
- [ ] **批量操作优化**
  - `get()` 批量获取的并行化
  - 减少锁竞争

### 2. 调度算法优化

- [ ] **数据本地性调度**
  - 任务尽量调度到数据所在的 Worker
- [ ] **优先级队列**
  - 支持任务优先级
- [ ] **负载均衡**
  - 动态调整任务分配策略

### 3. 容错和可靠性

- [ ] **任务重试**
  - Worker 崩溃后重新调度任务
- [ ] **Checkpoint**
  - 定期保存状态
- [ ] **异常传播**
  - Worker 异常传回主进程

### 4. 分布式扩展

- [ ] **跨机器通信**
  - 使用 gRPC 替换本地通信
  - 对象跨节点传输
- [ ] **GCS（全局控制存储）**
  - 使用 Redis 存储元数据
  - 集群状态管理

### 5. 监控和调试

- [ ] **可视化 Dashboard**
  - 任务执行状态
  - Worker 负载情况
- [ ] **性能分析**
  - 任务执行时间统计
  - 对象传输开销分析
- [ ] **日志系统**
  - 分布式日志收集

---

## 📂 推荐的项目结构

```
mini-ray/
├── README.md
├── doc/
│   ├── DESIGN.md           # 本文档
│   ├── API.md              # API 文档
│   └── TUTORIAL.md         # 使用教程
├── CMakeLists.txt          # 根构建文件
├── setup.py                # Python 包配置
│
├── cpp/                    # C++ 核心层
│   ├── CMakeLists.txt
│   ├── include/
│   │   └── miniray/
│   │       ├── common/
│   │       │   ├── id.h            # ObjectID, TaskID 等
│   │       │   ├── buffer.h        # 数据缓冲区
│   │       │   └── task.h          # Task 定义
│   │       ├── object_store/
│   │       │   └── object_store.h
│   │       ├── scheduler/
│   │       │   └── scheduler.h
│   │       └── core_worker/
│   │           └── core_worker.h
│   └── src/
│       ├── common/
│       │   ├── id.cpp
│       │   └── task.cpp
│       ├── object_store/
│       │   └── object_store.cpp
│       ├── scheduler/
│       │   └── scheduler.cpp
│       ├── core_worker/
│       │   └── core_worker.cpp
│       └── python_bindings.cpp     # pybind11 绑定
│
├── miniray/                # Python 封装层
│   ├── __init__.py         # 导出公共 API
│   ├── api.py              # init(), get(), remote()
│   ├── actor.py            # ActorClass, ActorHandle
│   ├── worker.py           # Worker 进程逻辑
│   └── _private/
│       └── serialization.py
│
├── examples/               # 示例代码
│   ├── 01_basic_task.py
│   ├── 02_actor.py
│   └── 03_mapreduce.py
│
└── tests/                  # 测试
    ├── test_object_store.py
    ├── test_scheduler.py
    ├── test_api.py
    └── test_actor.py
```

---

## 🎯 总结

**Mini-Ray 是一个高度还原 Ray 架构的教学项目**

### 核心目标

> 通过 **Python/C++ 异构实现**，深入理解分布式计算框架的核心原理，
> 体验真实 Ray 的工程架构和设计哲学。

### 技术栈

- **C++ 核心**：ObjectStore, Scheduler, CoreWorker
- **Python 封装**：API 层、Actor 层、序列化
- **绑定层**：pybind11
- **构建系统**：CMake + setuptools
- **通信**：共享内存 + POSIX IPC

### 预期代码量

- C++ 核心：~1000-1500 行
- Python 封装：~500 行
- pybind11 绑定：~200 行
- **总计**：~2000 行（高质量、可读性强的代码）

### 你将收获

1. **深刻理解 Ray 的设计**
2. **掌握 Python/C++ 混合编程**
3. **学会系统编程技术**（共享内存、多线程、IPC）
4. **积累分布式系统经验**
5. **一个可以放到简历上的项目** 😊

---

## 🚀 开始你的 Ray 学习之旅！

建议学习路径：

1. **Week 1-2**: 阅读 Ray 论文，理解核心概念
2. **Week 3-4**: 实现 Phase 1（C++ 基础 + ObjectStore）
3. **Week 5-6**: 实现 Phase 2（Scheduler + Worker）
4. **Week 7**: 实现 Phase 3（Python API）
5. **Week 8**: 实现 Phase 4（Actor）
6. **Week 9+**: 扩展和优化

**记住**：重点不是功能完整性，而是**理解核心设计原理**！

祝你学习愉快！🎉

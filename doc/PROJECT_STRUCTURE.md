# Mini-Ray 项目结构说明

> **最后更新**: 2024-12-06 (Phase 2.5 重构后)
>
> 本文档详细说明 Mini-Ray 项目的目录组织和文件用途。

---

## 📂 完整目录树

```
mini-ray/                           # 项目根目录
├── README.md                       # 项目主文档（快速开始指南）
├── REFACTORING_SUMMARY.md          # Phase 2.5 重构总结
├── .gitignore                      # Git 忽略配置
├── setup.py                        # Python 包安装和 C++ 构建配置
├── CMakeLists.txt                  # CMake 顶层配置
│
├── doc/                            # 📚 文档目录
│   ├── README.md                   # 文档索引（本目录导航）
│   ├── DESIGN.md                   # 系统架构设计文档
│   ├── CMAKE_GUIDE.md              # CMake 构建系统详解
│   ├── PROJECT_STRUCTURE.md        # 本文件（项目结构详解）
│   ├── PHASE1_SUMMARY.md           # Phase 1 完成总结
│   ├── PHASE2_GUIDE.md             # Phase 2 实现指南
│   └── PHASE3_DESIGN.md            # Phase 3 设计文档
│
├── cpp/                            # 🔧 C++ 核心层
│   ├── CMakeLists.txt              # C++ 构建配置
│   ├── include/miniray/            # 头文件目录
│   │   ├── common/                 # 通用基础设施
│   │   │   ├── id.h                # ObjectID 实现
│   │   │   ├── object_ref.h        # ObjectRef 实现
│   │   │   ├── task.h              # Task 数据结构
│   │   │   ├── buffer.h            # Buffer 数据结构
│   │   │   └── memory.h            # 共享内存管理（NEW）
│   │   ├── object_store/           # 对象存储模块（NEW）
│   │   │   └── object_store.h      # ObjectStore 实现
│   │   ├── raylet/                 # 调度器模块（NEW）
│   │   │   └── scheduler.h         # Scheduler 实现
│   │   └── core_worker/            # CoreWorker
│   │       └── core_worker.h       # CoreWorker 实现
│   └── src/                        # 实现文件目录
│       ├── common/                 # 通用模块实现
│       │   └── memory.cpp          # 共享内存实现（NEW）
│       ├── object_store/           # 对象存储实现（NEW）
│       │   └── object_store.cpp
│       ├── raylet/                 # 调度器实现（NEW）
│       │   └── scheduler.cpp
│       ├── core_worker/            # CoreWorker 实现
│       │   └── core_worker.cpp
│       └── python_bindings.cpp     # pybind11 绑定层
│
├── python/miniray/                 # 🐍 Python API 层
│   ├── __init__.py                 # 包初始化
│   ├── api.py                      # 用户 API (@ray.remote, ray.get)
│   ├── core.py                     # 核心功能封装
│   ├── actor.py                    # Actor 模型 (Phase 3)
│   ├── scheduler.py                # 调度器包装
│   ├── worker.py                   # Worker 进程逻辑
│   ├── _private/                   # 内部实现（不暴露给用户）
│   └── _miniray_core.*.so          # C++ 编译产物（动态库）
│
├── tests/                          # 🧪 测试目录
│   ├── __init__.py                 # 测试包初始化
│   ├── conftest.py                 # pytest 配置和 fixtures
│   ├── test_object_store.py        # 对象存储测试（8 个测试）
│   ├── test_scheduler.py           # 调度器测试（6 个测试）
│   ├── demo_phase1.py              # Phase 1 演示脚本
│   ├── demo_phase2.py              # Phase 2 演示脚本
│   └── demo_shared_memory.py       # 共享内存演示脚本
│
├── examples/                       # 📝 示例目录
│   ├── README.md                   # 示例说明文档
│   ├── __init__.py
│   ├── 01_object_store.py          # 对象存储基础示例
│   ├── 02_scheduler.py             # 调度器基础示例
│   ├── 03_simple_task.py           # 简单任务执行示例
│   └── 01_phase1_object_store.py   # 旧 Phase 1 示例
│
├── .venv/                          # Python 虚拟环境（本地开发）
└── build/                          # CMake 构建输出（自动生成）
```

---

## 🏗️ 架构层次

Mini-Ray 采用**三层架构**：

```
┌─────────────────────────────────────────────────┐
│          用户代码 (User Code)                    │
│    import miniray as ray                        │
│    @ray.remote                                  │
│    def func():                                  │
│        pass                                     │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│       Python API 层 (python/miniray/)           │
│  - api.py: @ray.remote, ray.get                │
│  - core.py: 核心逻辑封装                        │
│  - worker.py: Worker 进程管理                   │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│    Python/C++ 绑定层 (python_bindings.cpp)      │
│  - pybind11 自动生成 Python 绑定                │
│  - 类型转换（Python ↔ C++）                    │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│         C++ 核心层 (cpp/src/ & include/)        │
│                                                 │
│  ┌──────────────┐  ┌──────────────┐           │
│  │ ObjectStore  │  │  Scheduler   │           │
│  │ (对象存储)   │  │  (调度器)    │           │
│  └──────────────┘  └──────────────┘           │
│         ↓                  ↓                    │
│  ┌──────────────────────────────────┐          │
│  │   SharedMemory (共享内存基础)    │          │
│  └──────────────────────────────────┘          │
└─────────────────────────────────────────────────┘
```

---

## 📦 核心模块说明

### 1. Common 模块 (`cpp/include/miniray/common/`)

提供基础数据结构和工具：

| 文件 | 功能 | 说明 |
|------|------|------|
| `id.h` | ObjectID | 128 位唯一标识符 |
| `object_ref.h` | ObjectRef | 对象引用（包装 ObjectID） |
| `task.h` | Task | 任务数据结构 |
| `buffer.h` | Buffer | 数据缓冲区 |
| `memory.h` | SharedMemory | POSIX 共享内存封装（NEW） |

**设计要点**:
- 所有 ID 都基于随机生成，确保全局唯一
- ObjectRef 是值类型，可以安全拷贝和传递
- SharedMemory 使用 RAII 模式自动管理资源

---

### 2. ObjectStore 模块 (`cpp/include/miniray/object_store/`)

**重构说明**: 原来的 `shared::SharedObjectStore` 重命名为 `object_store::ObjectStore`

**核心功能**:
```cpp
namespace miniray {
namespace object_store {

class ObjectStore {
public:
    // 存储对象（自动生成 ID）
    ObjectRef Put(const std::vector<uint8_t>& data);

    // 存储对象（使用指定 ID）
    ObjectRef Put(const ObjectRef& ref, const std::vector<uint8_t>& data);

    // 获取对象
    std::shared_ptr<Buffer> Get(const ObjectRef& ref);

    // 删除对象
    void Delete(const ObjectRef& ref);

    // 检查对象是否存在
    bool Contains(const ObjectRef& ref) const;
};

}  // namespace object_store
}  // namespace miniray
```

**内存布局**:
- 固定大小：1000 个槽位
- 每个对象最大 64KB
- 使用共享内存，进程间零拷贝

---

### 3. Raylet 模块 (`cpp/include/miniray/raylet/`)

**重构说明**: 原来的 `shared::SharedScheduler` 重命名为 `raylet::Scheduler`

**核心功能**:
```cpp
namespace miniray {
namespace raylet {

class Scheduler {
public:
    // 提交任务
    void SubmitTask(const Task& task);

    // 获取下一个任务
    std::shared_ptr<Task> GetNextTask();

    // Worker 管理
    void RegisterWorker(int worker_id);
    void UnregisterWorker(int worker_id);
    void MarkWorkerBusy(int worker_id);
    void MarkWorkerIdle(int worker_id);
};

}  // namespace raylet
}  // namespace miniray
```

**调度策略**:
- FIFO 队列（先进先出）
- 循环队列实现（固定大小）
- Worker 拉取模式（Pull-based）

---

### 4. CoreWorker 模块 (`cpp/include/miniray/core_worker/`)

**Facade 模式**: 封装 Scheduler 和 ObjectStore 的复杂性

```cpp
namespace miniray {
namespace core_worker {

class CoreWorker {
public:
    CoreWorker(
        std::shared_ptr<raylet::Scheduler> scheduler,
        std::shared_ptr<object_store::ObjectStore> object_store,
        int worker_id
    );

    // 任务操作
    ObjectRef SubmitTask(const Task& task);
    std::shared_ptr<Task> GetNextTask();

    // 对象操作
    void PutObject(const ObjectRef& ref, const std::vector<uint8_t>& data);
    std::shared_ptr<Buffer> GetObject(const ObjectRef& ref);

    // Worker 状态
    void MarkWorkerBusy();
    void MarkWorkerIdle();
};

}  // namespace core_worker
}  // namespace miniray
```

---

## 🐍 Python API 层

### 主要文件

#### `api.py` - 用户接口
```python
# 装饰器
@ray.remote
def my_function(x):
    return x * 2

# 执行
ref = my_function.remote(21)
result = ray.get(ref)  # 42
```

#### `core.py` - 核心逻辑
```python
class GlobalState:
    """全局状态管理"""
    scheduler: Scheduler
    object_store: ObjectStore
    worker: CoreWorker
```

#### `worker.py` - Worker 进程
```python
class Worker:
    """Worker 进程主循环"""
    def run(self):
        while True:
            task = get_next_task()
            if task:
                execute_task(task)
```

---

## 🔄 Phase 2.5 重构变更

### 命名空间变更

| 旧命名空间 | 新命名空间 | 文件位置 |
|-----------|-----------|---------|
| `miniray::shared::SharedMemory` | `miniray::common::SharedMemory` | `common/memory.h` |
| `miniray::shared::SharedObjectStore` | `miniray::object_store::ObjectStore` | `object_store/object_store.h` |
| `miniray::shared::SharedScheduler` | `miniray::raylet::Scheduler` | `raylet/scheduler.h` |

### 目录结构变更

```
旧结构:
cpp/include/miniray/shared/
  ├── shared_memory.h
  ├── shared_object_store.h
  └── shared_scheduler.h

新结构:
cpp/include/miniray/
  ├── common/memory.h
  ├── object_store/object_store.h
  └── raylet/scheduler.h
```

### 代码分离

所有模块现在都有独立的实现文件：
- `cpp/src/common/memory.cpp`
- `cpp/src/object_store/object_store.cpp`
- `cpp/src/raylet/scheduler.cpp`

---

## 🧪 测试结构

### 测试文件组织

```
tests/
├── conftest.py              # pytest 配置
│   - cleanup_shared_memory fixture
│   - temp_object_store fixture
│   - temp_scheduler fixture
│
├── test_object_store.py     # ObjectStore 测试
│   - 8 个测试用例
│   - 覆盖 Put/Get/Delete/Contains
│
└── test_scheduler.py        # Scheduler 测试
    - 6 个测试用例
    - 覆盖任务提交、获取、Worker 管理
```

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_object_store.py -v

# 查看覆盖率
pytest tests/ --cov=miniray
```

---

## 📝 示例结构

### 示例文件

```
examples/
├── README.md                # 示例说明
├── 01_object_store.py       # 对象存储基础
├── 02_scheduler.py          # 调度器基础
└── 03_simple_task.py        # 完整任务流程
```

### 运行示例

```bash
# 对象存储示例
python examples/01_object_store.py

# 调度器示例
python examples/02_scheduler.py

# 任务执行示例
python examples/03_simple_task.py
```

---

## 🔧 构建流程

### 1. CMake 配置
```bash
cmake -B build -S .
```

### 2. 编译 C++ 代码
```bash
cmake --build build
```

### 3. 安装 Python 包
```bash
pip install -e .
```

**自动化**: `pip install -e .` 会自动执行上述步骤

---

## 📚 代码注释风格

所有 C++ 代码都遵循详细的注释规范：

### 文件级注释
```cpp
/**
 * file_name.h - 简短描述
 *
 * ============================================================
 * 设计思想和架构
 * ============================================================
 * [详细的设计说明]
 *
 * ============================================================
 * C++ 特性运用
 * ============================================================
 * [使用的 C++ 技术和最佳实践]
 */
```

### 类级注释
```cpp
/**
 * @brief 类的简短描述
 *
 * 详细说明：
 * - 功能
 * - 使用场景
 * - 注意事项
 */
class MyClass {
    // ...
};
```

### 方法级注释
```cpp
/**
 * @brief 方法简短描述
 *
 * @param param1 参数说明
 * @return 返回值说明
 *
 * 实现细节：
 * 1. 步骤一
 * 2. 步骤二
 */
void MyMethod(int param1);
```

---

## 🔍 查找代码

### 按功能查找

| 功能 | 位置 |
|------|------|
| 对象存储 | `cpp/include/miniray/object_store/` |
| 任务调度 | `cpp/include/miniray/raylet/` |
| 共享内存 | `cpp/include/miniray/common/memory.h` |
| Python API | `python/miniray/api.py` |
| Worker 逻辑 | `python/miniray/worker.py` |

### 按文件类型查找

```bash
# 查找所有头文件
find cpp/include -name "*.h"

# 查找所有实现文件
find cpp/src -name "*.cpp"

# 查找所有 Python 文件
find python/miniray -name "*.py"

# 查找所有测试文件
find tests -name "test_*.py"
```

---

## 📖 相关文档

- **[DESIGN.md](DESIGN.md)** - 系统架构设计
- **[PHASE1_SUMMARY.md](PHASE1_SUMMARY.md)** - Phase 1 总结
- **[PHASE2_GUIDE.md](PHASE2_GUIDE.md)** - Phase 2 指南
- **[PHASE3_DESIGN.md](PHASE3_DESIGN.md)** - Phase 3 设计
- **[../REFACTORING_SUMMARY.md](../REFACTORING_SUMMARY.md)** - 重构总结

---

**最后更新**: 2024-12-06
**维护者**: Mini-Ray Team

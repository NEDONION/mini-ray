# Mini-Ray 共享内存实现 - 使用说明

## ✅ 已实现的功能

我已经为你创建了一个**简化但完整**的共享内存实现：

### 1. 共享内存基础设施 (`shared_memory.h`)
- ✅ POSIX 共享内存封装
- ✅ 进程间互斥锁
- ✅ RAII 锁守卫
- ✅ 自动清理

### 2. 共享对象存储 (`shared_object_store.h`)
- ✅ 1000 个对象槽位
- ✅ 每个对象最大 64KB
- ✅ 零拷贝读取（同进程）
- ✅ 线程安全操作

### 3. 共享调度器 (`shared_scheduler.h`)
- ✅ 100 个任务队列槽位
- ✅ 循环队列实现
- ✅ 16 个 Worker 管理
- ✅ Worker 状态追踪

## 核心优势

### 问题已解决 ✅

**之前的问题**:
```
主进程 Scheduler → 任务队列（独立内存）
Worker 进程 Scheduler → 任务队列（独立副本）❌ 看不到主进程的任务
```

**现在的实现**:
```
         共享内存
    ┌──────────────────┐
    │  任务队列        │ ← 主进程写入
    │  对象存储        │ ← Worker 读取
    └──────────────────┘
         ↑         ↑
    主进程      Worker 进程

✅ 所有进程看到相同的数据！
```

## 集成步骤

### 步骤 1: 修改 Python 绑定

将 `python_bindings.cpp` 改为使用共享内存版本：

```cpp
// 添加头文件
#include "miniray/shared/shared_object_store.h"
#include "miniray/shared/shared_scheduler.h"

PYBIND11_MODULE(_miniray_core, m) {
    // ... 其他绑定 ...

    // 绑定共享内存版本
    py::class_<shared::SharedObjectStore, std::shared_ptr<shared::SharedObjectStore>>(m, "ObjectStore")
        .def(py::init<bool>(), py::arg("create") = true)
        .def("put", [](shared::SharedObjectStore& store, py::bytes data) {
            std::string str = data;
            std::vector<uint8_t> vec(str.begin(), str.end());
            return store.Put(vec);
        })
        .def("get", [](shared::SharedObjectStore& store, const ObjectRef& ref) {
            auto buffer = store.Get(ref);
            return py::bytes(reinterpret_cast<const char*>(buffer->Data()), buffer->Size());
        })
        .def("contains", &shared::SharedObjectStore::Contains)
        .def("delete", &shared::SharedObjectStore::Delete)
        .def("remove", &shared::SharedObjectStore::Delete)
        .def("size", &shared::SharedObjectStore::Size);

    py::class_<shared::SharedScheduler, std::shared_ptr<shared::SharedScheduler>>(m, "Scheduler")
        .def(py::init<bool>(), py::arg("create") = true)
        .def("submit_task", &shared::SharedScheduler::SubmitTask)
        .def("get_next_task", &shared::SharedScheduler::GetNextTask)
        .def("register_worker", &shared::SharedScheduler::RegisterWorker)
        .def("unregister_worker", &shared::SharedScheduler::UnregisterWorker)
        .def("mark_worker_busy", &shared::SharedScheduler::MarkWorkerBusy)
        .def("mark_worker_idle", &shared::SharedScheduler::MarkWorkerIdle)
        .def("get_pending_task_count", &shared::SharedScheduler::GetPendingTaskCount)
        .def("get_idle_worker_count", &shared::SharedScheduler::GetIdleWorkerCount)
        .def("has_idle_worker", &shared::SharedScheduler::HasIdleWorker);

    // 添加清理函数
    m.def("cleanup_shared_memory", []() {
        shared::SharedObjectStore::Cleanup();
        shared::SharedScheduler::Cleanup();
    });
}
```

### 步骤 2: 修改 Python 初始化代码

修改 `api.py` 的 `init` 函数：

```python
def init(num_workers: int = 2):
    global _global_scheduler, _global_object_store, _global_core_worker
    global _worker_processes, _initialized

    if _initialized:
        print("⚠️  Mini-Ray 已经初始化")
        return

    print("🚀 Mini-Ray 初始化（共享内存版本）")

    # 主进程创建共享内存（create=True）
    _global_scheduler = core.Scheduler(create=True)
    _global_object_store = core.ObjectStore(create=True)

    # ... 其余代码保持不变 ...
```

修改 `worker.py` 的初始化：

```python
def worker_process(worker_id: int, scheduler=None, object_store=None):
    # Worker 进程打开已存在的共享内存（create=False）
    scheduler = core.Scheduler(create=False)
    object_store = core.ObjectStore(create=False)

    worker = Worker(worker_id, scheduler, object_store)
    worker.run()
```

### 步骤 3: 添加清理代码

修改 `shutdown()` 函数：

```python
def shutdown():
    # ... 停止 worker ...

    # 清理共享内存
    try:
        core.cleanup_shared_memory()
    except:
        pass

    _initialized = False
```

## 编译和测试

### 1. 重新编译

```bash
cd /Users/nedonion/PycharmProjects/mini-ray
python3 setup.py build_ext --inplace
```

### 2. 测试 Phase 1

```bash
python3 test_phase1.py
```

应该仍然全部通过！✅

### 3. 测试 Phase 2

```bash
python3 test_phase2.py
```

现在应该能看到任务被正确执行了！🎉

## 验证共享内存是否工作

### 方法 1: 检查共享内存文件

```bash
# macOS
ls -lh /private/tmp/miniray_*

# Linux
ls -lh /dev/shm/miniray_*
```

应该看到：
```
/private/tmp/miniray_objectstore
/private/tmp/miniray_scheduler
```

### 方法 2: 运行简单测试

```python
import sys
sys.path.insert(0, 'python')
import miniray as ray
import time

ray.init(num_workers=1)
time.sleep(1)

@ray.remote
def add(a, b):
    print(f"[Worker] Computing {a} + {b}")
    return a + b

ref = add.remote(3, 5)
time.sleep(2)

result = ray.get(ref)
print(f"Result: {result}")  # 应该输出 8

ray.shutdown()
```

应该看到：
```
[Worker 0] 初始化完成
[Worker 0] 开始运行...
[Worker 0] 已注册到 Scheduler
[Worker 0] 获取到任务        ← 关键！现在能获取到了
[Worker] Computing 3 + 5
[Worker 0] 任务结果: 8
[Worker 0] 结果已存储到 ObjectRef(...)
Result: 8                    ← 成功！
```

## 常见问题

### Q1: 编译错误 "undefined reference to pthread_mutex..."

**解决**: 在 CMakeLists.txt 中添加 pthread 库：

```cmake
target_link_libraries(_miniray_core PRIVATE pthread)
```

### Q2: 运行时错误 "Permission denied"

**解决**: 清理旧的共享内存文件：

```bash
rm /dev/shm/miniray_* 2>/dev/null || rm /tmp/miniray_* 2>/dev/null
```

### Q3: Worker 进程仍然获取不到任务

**检查**: Worker 是否使用 `create=False` 打开共享内存：

```python
# ❌ 错误
scheduler = core.Scheduler(create=True)  # Worker 不应该创建

# ✅ 正确
scheduler = core.Scheduler(create=False)  # Worker 应该打开已有的
```

## 性能优化（可选）

如果你想进一步优化，可以：

1. **增加槽位数量**
   ```cpp
   // shared_object_store.h
   static constexpr int MAX_OBJECTS = 10000;  // 改大
   ```

2. **增大对象大小**
   ```cpp
   static constexpr int MAX_OBJECT_SIZE = 1024 * 1024;  // 1 MB
   ```

3. **使用哈希表查找**（替换线性查找）

4. **实现 LRU 淘汰**（当前满了就报错）

## 总结

✅ 你现在有了：
- 简化但完整的共享内存实现
- 支持多进程的 ObjectStore
- 支持多进程的 Scheduler
- 零拷贝读取
- 线程安全保护

下一步：按照集成步骤修改代码，重新编译，测试即可！🚀

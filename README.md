# Mini-Ray

> 一个采用 **Python/C++ 异构架构** 的简化版 Ray 分布式计算框架
>
> 通过模拟真实 Ray 的分层设计，深入理解分布式系统核心原理

---

## 📖 项目简介

Mini-Ray 是一个教学项目，高度还原 Ray 的核心架构：
- **C++ 核心层**：ObjectStore、Scheduler、CoreWorker（高性能）
- **Python 封装层**：用户友好的 API（易用性）
- **pybind11 绑定层**：Python ↔ C++ 互操作

**学习收益**：
- 分布式系统架构设计
- Python/C++ 混合编程
- 共享内存和进程间通信
- Ray 核心设计理念

---

## 🏗️ 项目架构

```
┌─────────────────────────────────────────┐
│     Python API (mini_ray.*)             │
│  init() / get() / remote() / Actor      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   pybind11 绑定层 (_miniray_core.so)    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         C++ 核心层 (cpp/)                │
│  ObjectStore / Scheduler / CoreWorker   │
└─────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 前置要求

- **Python 3.7+**
- **CMake 3.15+**
- **C++17 编译器**（GCC 7+, Clang 5+, MSVC 2017+）

### 安装依赖

```bash
# macOS
pip3 install --break-system-packages pybind11 setuptools

# Linux  
pip3 install pybind11 setuptools

# 或使用虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate
pip install pybind11 setuptools pytest pickle
```

### 构建项目

```bash
# 构建 C++ 扩展模块
python3 setup.py build_ext --inplace

# 构建成功后会生成：python/miniray/_miniray_core.cpython-xxx.so
```

### 验证安装

```bash
# 运行 Phase 1 验收测试
python3 test_phase1.py

# 运行 Phase 2 验收测试
python3 test_phase2.py
```

**期望输出**：
```
======================================================================
                        Phase 2 验收测试
======================================================================
...
总计: 7 个测试
通过: 7 个
失败: 0 个

🎉 所有测试通过！
```

---

## 🧪 测试

### 测试文件说明

| 文件 | 说明 | 用途 |
|------|------|------|
| **test_phase1.py** | Phase 1 验收测试 | 验证 C++ 核心模块 |
| **test_phase2.py** ⭐ | Phase 2 验收测试 | 验证任务调度和执行 |
| **tests/test_cpp_core.py** | 详细单元测试 | 完整测试所有组件 |

### 运行测试

```bash
# Phase 1 验收
python3 test_phase1.py

# Phase 2 验收（推荐）⭐
python3 test_phase2.py

# 详细测试
python3 tests/test_cpp_core.py
```

---

## 💡 使用示例

### Phase 1：使用 C++ ObjectStore

```python
import sys

sys.path.insert(0, 'python')  # 添加到路径

from miniray import _miniray_core as core
import pickle

# 创建 ObjectStore
store = core.ObjectStore()

# 存储数据
ref = store.put(b"Hello, Mini-Ray!")
print(f"ObjectRef: {ref}")

# 获取数据
data = store.get(ref)
print(f"数据: {data}")

# 存储 Python 对象
obj = {"result": 42}
ref2 = store.put(pickle.dumps(obj))
retrieved = pickle.loads(store.get(ref2))
print(f"对象: {retrieved}")
```

### Phase 2：高层 API（已完成 ✅）

```python
import miniray as ray

# 初始化系统
ray.init(num_workers=4)

# 定义远程函数
@ray.remote
def add(a, b):
   return a + b

# 调用远程函数
ref = add.remote(1, 2)
result = ray.get(ref)
print(result)  # 3

# 关闭系统
ray.shutdown()
```

---

## 📁 项目结构

```
mini-ray/                         # 项目根目录
├── README.md                     # 本文件
├── setup.py                      # 构建配置
├── CMakeLists.txt                # CMake 根配置
├── test_phase1.py                # Phase 1 验收测试
├── test_phase2.py                # Phase 2 验收测试 ⭐
│
├── python/                       # Python 代码目录
│   └── miniray/                  # Python 包（import miniray）
│       ├── __init__.py           # 包入口
│       ├── _miniray_core.so      # C++ 扩展模块 ⚙️
│       ├── api.py                # Python API (Phase 2) ✅
│       ├── worker.py             # Worker 进程 (Phase 2) ✅
│       ├── actor.py              # Actor 实现 (Phase 3)
│       └── core.py               # 核心数据结构
│
├── cpp/                          # C++ 代码目录
│   ├── CMakeLists.txt            # C++ 构建配置
│   ├── include/miniray/          # C++ 头文件
│   │   ├── common/
│   │   │   ├── id.h             # ObjectID（128-bit UUID）
│   │   │   ├── object_ref.h     # ObjectRef 引用
│   │   │   └── task.h           # Task 数据结构
│   │   ├── object_store/
│   │   │   └── object_store.h   # 对象存储（线程安全）
│   │   ├── scheduler/           # (Phase 2) ✅
│   │   │   └── scheduler.h      # Scheduler 任务调度器
│   │   └── core_worker/         # (Phase 2) ✅
│   │       └── core_worker.h    # CoreWorker 核心工作器
│   └── src/
│       ├── python_bindings.cpp  # pybind11 绑定
│       ├── scheduler/
│       │   └── scheduler.cpp    # (Phase 2) ✅
│       └── core_worker/
│           └── core_worker.cpp  # (Phase 2) ✅
│
├── tests/
│   └── test_cpp_core.py         # 详细单元测试
│
├── examples/                     # 示例代码
│   ├── phase2_01_basic_tasks.py           # 基础任务示例 ✅
│   ├── phase2_02_parallel_computation.py  # 并行计算示例 ✅
│   └── phase2_03_performance_comparison.py # 性能对比示例 ✅
│
└── doc/                          # 文档
    ├── DESIGN.md                # 设计文档（详细架构）
    ├── PHASE1_SUMMARY.md        # Phase 1 总结
    └── PHASE2_GUIDE.md          # Phase 2 使用指南 ✅
```

---

## 🛠️ 开发指南

### 修改 C++ 代码后重新编译

```bash
# 清理旧构建
rm -rf build/

# 重新构建
python3 setup.py build_ext --inplace

# 测试
python3 test_phase1.py
```

### 调试 C++ 代码

```bash
# Debug 模式构建
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Debug ..
cmake --build .

# 使用 GDB/LLDB 调试
gdb --args python3 ../test_phase1.py
```

### 添加新的 C++ 类

1. 在 `cpp/include/miniray/` 创建头文件
2. 在 `cpp/src/python_bindings.cpp` 添加 pybind11 绑定
3. 重新编译
4. 在 Python 中使用：
   ```python
   import sys
   sys.path.insert(0, 'python')
   from miniray import _miniray_core
   ```

---

## 📊 开发进度

### ✅ Phase 1：C++ 核心基础设施（已完成）

- [x] ObjectID（128-bit UUID）
- [x] ObjectRef（对象引用）
- [x] ObjectStore（线程安全对象存储）
- [x] Task 数据结构
- [x] pybind11 绑定
- [x] CMake 构建系统
- [x] 验收测试

**验收标准**：能够存储和获取 Python 对象 ✅

### ✅ Phase 2：任务调度和执行（已完成）

- [x] Scheduler（C++ 任务调度器）
- [x] CoreWorker（C++ 核心工作组件）
- [x] Worker 进程管理
- [x] Python API 层（`@ray.remote`、`ray.get()`）
- [x] 端到端任务执行
- [x] 验收测试
- [x] 示例代码

**验收标准**：✅ 通过
```python
@ray.remote
def add(a, b):
    return a + b

result = ray.get(add.remote(1, 2))  # 返回 3
```

**测试命令**：
```bash
# 运行 Phase 2 验收测试
python3 test_phase2.py

# 运行示例代码
python3 examples/phase2_01_basic_tasks.py
python3 examples/phase2_02_parallel_computation.py
python3 examples/phase2_03_performance_comparison.py
```

**详细文档**：[doc/PHASE2_GUIDE.md](doc/PHASE2_GUIDE.md)

### 📅 Phase 3-5（规划中）

- Phase 3: Actor 模型和自动依赖追踪
- Phase 4: 高级调度策略
- Phase 5: 容错和监控

详见 [doc/DESIGN.md](doc/DESIGN.md)

---

## 📚 学习资源

### 项目文档

- [doc/DESIGN.md](doc/DESIGN.md) - 详细架构设计
- [doc/PHASE1_SUMMARY.md](doc/PHASE1_SUMMARY.md) - Phase 1 总结
- [doc/PHASE2_GUIDE.md](doc/PHASE2_GUIDE.md) - Phase 2 使用指南 ⭐

### Ray 相关

- [Ray 官方文档](https://docs.ray.io/)
- [Ray 论文](https://arxiv.org/abs/1712.05889)
- [Ray GitHub](https://github.com/ray-project/ray)

### 技术栈

- [pybind11 文档](https://pybind11.readthedocs.io/)
- [CMake 教程](https://cmake.org/cmake/help/latest/guide/tutorial/index.html)
- [C++17 特性](https://en.cppreference.com/w/cpp/17)

---

## 📝 常见问题

### Q: 构建失败，找不到 pybind11？

```bash
pip3 install --break-system-packages pybind11
# 或在虚拟环境中
pip install pybind11
```

### Q: import mini_ray 失败？

确保：
1. 已成功构建：`python3 setup.py build_ext --inplace`
2. 正确添加路径：
   ```python
   import sys
   sys.path.insert(0, 'python')
   import miniray
   ```
3. 检查 `python/mini_ray/_miniray_core.so` 是否存在

### Q: macOS 出现 "dynamic_lookup" 警告？

这是正常的，不影响功能，可以忽略。

### Q: 如何使用虚拟环境？

```bash
python3 -m venv venv
source venv/bin/activate
pip install pybind11 setuptools
python setup.py build_ext --inplace
```
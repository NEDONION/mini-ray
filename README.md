# Mini-Ray

> 一个采用 **Python/C++ 异构架构** 的简化版 Ray 分布式计算框架
>
> 通过模拟真实 Ray 的分层设计，深入理解分布式系统核心原理

[![Tests](https://img.shields.io/badge/tests-14%20passed-success)](tests/)
[![Phase](https://img.shields.io/badge/phase-2.5%20completed-blue)](#开发进度)
[![Python](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/)
[![C++](https://img.shields.io/badge/C%2B%2B-17-blue)](https://isocpp.org/)

---

## 📖 项目简介

Mini-Ray 是一个**教学项目**，高度还原 Ray 的核心架构：
- **C++ 核心层**：ObjectStore、Scheduler、CoreWorker（高性能）
- **Python 封装层**：用户友好的 API（易用性）
- **pybind11 绑定层**：Python ↔ C++ 互操作

**学习收益**：
- ✅ 分布式系统架构设计
- ✅ Python/C++ 混合编程
- ✅ 共享内存和进程间通信
- ✅ Ray 核心设计理念

---

## 🏗️ 项目架构

### 三层架构设计

```
┌─────────────────────────────────────────────────┐
│       用户代码 (User Code)                       │
│   @ray.remote / ray.get() / ray.init()         │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│       Python API 层 (python/miniray/)           │
│   api.py / worker.py / core.py                 │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│    Python/C++ 绑定层 (python_bindings.cpp)      │
│   pybind11 自动生成的绑定代码                   │
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

### 核心模块

| 模块 | 位置 | 功能 |
|------|------|------|
| **ObjectStore** | `cpp/include/miniray/object_store/` | 对象存储（1000 槽位，64KB/对象） |
| **Scheduler** | `cpp/include/miniray/raylet/` | 任务调度（FIFO 队列） |
| **CoreWorker** | `cpp/include/miniray/core_worker/` | Worker 核心（Facade 模式） |
| **SharedMemory** | `cpp/include/miniray/common/memory.h` | POSIX 共享内存封装 |

---

## 🚀 快速开始

### 前置要求

- **Python 3.7+**
- **CMake 3.15+**
- **C++17 编译器**（GCC 7+, Clang 5+, MSVC 2017+）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/NEDONION/mini-ray.git
cd mini-ray

# 2. 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install --upgrade pip
# 仅 ML 依赖
pip install -r ml/requirements.txt
# 完整项目依赖
pip install -r requirements.txt

# 4. 构建 C++ 扩展模块
pip install -e .

# 5. 验证安装
pytest tests/ -v
```

### GPU Server 拉取项目

```bash
# 如果没有 unzip 先装一个
sudo apt update
sudo apt install -y unzip

# 用 codeload 下 zip（比 git 稳很多）
wget --no-check-certificate \
  https://codeload.github.com/NEDONION/mini-ray/zip/refs/heads/main \
  -O mini-ray.zip

# 解压
unzip mini-ray.zip
mv mini-ray-main mini-ray
rm mini-ray.zip

cd mini-ray

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# pybind11 安装可能有问题
pip uninstall -y pybind11
pip install "pybind11[global]"

pip install -e .

pytest tests/ -v
```

### GPU Server 重新拉取项目

```bash
cd ~   # 或你想放的目录
# 重新下载新版
wget --no-check-certificate \
  https://codeload.github.com/NEDONION/mini-ray/zip/refs/heads/main \
  -O mini-ray.zip

unzip -o mini-ray.zip  # -o 覆盖旧文件
rm mini-ray.zip

# 覆盖旧目录
rm -rf mini-ray
mv mini-ray-main mini-ray

cd mini-ray

# 如果创建虚拟环境报错
hash -r

python3 -m venv .venv
source .venv/bin/activate

# 重新安装 Python 依赖（如果 requirements 有变化）
pip install -r requirements.txt

# pybind11 安装可能有问题
pip uninstall -y pybind11
pip install "pybind11[global]"

# 重新构建 C++ 模块
pip install -e .
```

### GPU Server 数据集下载

```bash
# 用官方源 + 多线程下载
cd /root/mini-ray/data
aria2c -x 16 -s 16 \
  -o cifar-10-python.tar.gz \
  "https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz"

tar -xzf cifar-10-python.tar.gz
rm cifar-10-python.tar.gz
```

```bash
# /autodl-pub/data
cd /autodl-pub/data

# 已经有的数据集
ADEChallengeData2016  CULane      GOT10k                      MOT20                   TT100K               cityscapes
Aishell               CelebA      ILSVRC2015                  ModelNet                TrackingNet          horse2zebra.zip
BERT-Pretrain-Model   CrowdHuman  ImageNet                    NUSWIDE                 VOCdevkit            mot17
CASIAWebFace          DIV2K       ImageNet-mini               Objects365              Vimeo-90k            mpii_human_pose
CMLR                  DOTA        KITTI                       RoBERTa-Pretrain-Model  argoverse2.0-sensor  mvtec_anomaly_detection.tar.xz
COCO2017              DRIVE       KITTI_Depth_Completion.tar  S3DIS                   cifar-10             nuScenes
CUB200-2011           Flickr2K    LaSOT                       SemanticKITTI           cifar-100            vangogh2photo.zip
```

### GPU Server Training/Inference Demo
- **Dataset (CIFAR-10)**
  - 60k 32×32 RGB images, 10 classes.
- **GPU (RTX 5090)**
  - 32GB VRAM, high-throughput CUDA/FP16/BF16.
- **Model (GAN)**
  - GAN: minimax adversarial generator–discriminator training.
  ![](https://raw.githubusercontent.com/NEDONION/my-pics-space/main/20251209004034.png)

```bash
# Single-Node Multi-Process Training
python -m ml.gan.train --mode distributed --workers 8 --epochs 100 --sync-interval 5
```
![](https://raw.githubusercontent.com/NEDONION/my-pics-space/main/20251209003856.png)

```bash
# Single-Node Multi-Process Inference
python -m ml.gan.generate --model ./models/gan/worker_0/generator_0.pth --num-images 10 --distributed --workers 4
```
![](https://raw.githubusercontent.com/NEDONION/my-pics-space/main/20251209003845.png)

显存使用情况 `nvtop`
![](https://raw.githubusercontent.com/NEDONION/my-pics-space/main/20251209004214.png)

### 验证安装

```bash
# 运行所有测试（应该看到 14 个测试通过）
pytest tests/ -v

# 运行示例
python examples/01_object_store.py
python examples/02_scheduler.py
python examples/03_simple_task.py
```

**期望输出**：
```
============================== 14 passed in 0.15s ===============================
✓ 示例 1 完成
✓ 示例 2 完成
✓ 示例 3 完成
```

---

## 💡 使用示例

### 示例 1：对象存储

```python
import pickle
import miniray._miniray_core as core

# 创建对象存储
store = core.ObjectStore(create=True)

# 存储数据
data = b"Hello, Mini-Ray!"
ref = store.put(data)

# 获取数据
retrieved = store.get(ref)
print(retrieved)  # b"Hello, Mini-Ray!"

# 存储 Python 对象
obj = {"result": 42, "data": [1, 2, 3]}
ref2 = store.put(pickle.dumps(obj))
retrieved_obj = pickle.loads(store.get(ref2))
print(retrieved_obj)  # {'result': 42, 'data': [1, 2, 3]}
```

### 示例 2：任务调度

```python
import pickle
import miniray._miniray_core as core

def square(x):
    return x * x

# 创建调度器
scheduler = core.Scheduler(create=True)

# 创建任务
task = core.Task()
task.return_ref = core.ObjectRef()
task.serialized_function = list(pickle.dumps(square))
task.serialized_args = list(pickle.dumps((5,)))

# 提交任务
scheduler.submit_task(task)

# 获取任务
retrieved_task = scheduler.get_next_task()

# 执行任务
func = pickle.loads(bytes(retrieved_task.serialized_function))
args = pickle.loads(bytes(retrieved_task.serialized_args))
result = func(*args)
print(result)  # 25
```

### 示例 3：完整工作流（Python API）

```python
import miniray as ray

# 初始化（Phase 3 将实现）
# ray.init(num_workers=4)

# 定义远程函数
@ray.remote
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

# 调用远程函数
ref = fibonacci.remote(10)
result = ray.get(ref)
print(result)  # 55
```

---

## 📁 项目结构

```
mini-ray/                           # 项目根目录
├── README.md                       # 本文件（项目主页 + 文档导航）
├── REFACTORING_SUMMARY.md          # Phase 2.5 重构总结
├── setup.py                        # Python 包构建配置
├── CMakeLists.txt                  # CMake 顶层配置
│
├── cpp/                            # 🔧 C++ 核心层
│   ├── CMakeLists.txt              # C++ 构建配置
│   ├── include/miniray/            # 头文件目录
│   │   ├── common/                 # 通用基础设施
│   │   │   ├── id.h                # ObjectID（128-bit UUID）
│   │   │   ├── object_ref.h        # ObjectRef 引用
│   │   │   ├── task.h              # Task 数据结构
│   │   │   ├── buffer.h            # Buffer 缓冲区
│   │   │   └── memory.h            # 共享内存管理
│   │   ├── object_store/           # 对象存储模块
│   │   │   └── object_store.h      # ObjectStore 实现
│   │   ├── raylet/                 # 调度器模块
│   │   │   └── scheduler.h         # Scheduler 实现
│   │   └── core_worker/            # CoreWorker
│   │       └── core_worker.h       # CoreWorker 实现
│   └── src/                        # 实现文件目录
│       ├── common/memory.cpp
│       ├── object_store/object_store.cpp
│       ├── raylet/scheduler.cpp
│       ├── core_worker/core_worker.cpp
│       └── python_bindings.cpp     # pybind11 绑定
│
├── python/miniray/                 # 🐍 Python API 层
│   ├── __init__.py                 # 包初始化
│   ├── api.py                      # 用户 API (@ray.remote, ray.get)
│   ├── core.py                     # 核心功能封装
│   ├── actor.py                    # Actor 模型 (Phase 3)
│   ├── scheduler.py                # 调度器包装
│   ├── worker.py                   # Worker 进程逻辑
│   └── _miniray_core.*.so          # C++ 编译产物（动态库）
│
├── tests/                          # 🧪 测试目录（14 个测试）
│   ├── conftest.py                 # pytest 配置和 fixtures
│   ├── test_object_store.py        # 对象存储测试（8 个）
│   ├── test_scheduler.py           # 调度器测试（6 个）
│   ├── demo_phase1.py              # Phase 1 演示脚本
│   ├── demo_phase2.py              # Phase 2 演示脚本
│   └── demo_shared_memory.py       # 共享内存演示脚本
│
├── examples/                       # 📝 示例目录（3 个示例）
│   ├── README.md                   # 示例说明文档
│   ├── 01_object_store.py          # 对象存储基础示例
│   ├── 02_scheduler.py             # 调度器基础示例
│   └── 03_simple_task.py           # 简单任务执行示例
│
└── doc/                            # 📚 文档目录
    ├── DESIGN.md                   # 系统架构设计文档
    ├── CMAKE_GUIDE.md              # CMake 构建系统详解
    ├── PROJECT_STRUCTURE.md        # 项目结构详解
    ├── PHASE1_SUMMARY.md           # Phase 1 完成总结
    ├── PHASE2_GUIDE.md             # Phase 2 实现指南
    └── PHASE3_DESIGN.md            # Phase 3 设计文档 ⭐ NEW!
```

---

## 📊 开发进度

### ✅ Phase 1：对象存储（已完成）

**核心功能**：
- [x] ObjectID（128-bit 唯一标识符）
- [x] ObjectRef（对象引用）
- [x] ObjectStore（线程安全对象存储）
- [x] Buffer（数据缓冲区）
- [x] pybind11 绑定
- [x] CMake 构建系统

**验收标准**：✅ 能够存储和获取 Python 对象

**文档**：[doc/PHASE1_SUMMARY.md](doc/PHASE1_SUMMARY.md)

---

### ✅ Phase 2：任务调度（已完成）

**核心功能**：
- [x] Scheduler（任务调度器，FIFO 队列）
- [x] CoreWorker（核心工作组件，Facade 模式）
- [x] Task 数据结构
- [x] Worker 管理（注册、状态管理）
- [x] Python API 层基础

**验收标准**：✅ 能够提交和执行任务

**文档**：[doc/PHASE2_GUIDE.md](doc/PHASE2_GUIDE.md)

---

### 🔄 Phase 3：Actor + ML 工作流 + Dashboard（规划中）

**核心功能**（详见设计文档）：
- [ ] **Actor 模型**（有状态的分布式对象）
  - [ ] `@ray.remote` 装饰类
  - [ ] `Actor.remote()` 创建实例
  - [ ] `actor.method.remote()` 调用方法
  - [ ] Actor 状态管理和路由

- [ ] **超参数调优框架**（实用的 ML 应用）
  - [ ] `tune.run()` API
  - [ ] 网格搜索（Grid Search）
  - [ ] 随机搜索（Random Search）
  - [ ] 结果追踪和可视化

- [ ] **Dashboard 监控面板**（Web UI）
  - [ ] 实时任务监控
  - [ ] 依赖图可视化
  - [ ] 性能指标图表
  - [ ] Actor 状态面板

**时间规划**：3-4 周
- Week 1: Actor 模型
- Week 2: 超参数调优
- Week 3: Dashboard
- Week 4: 集成和优化

**详细设计**：[doc/PHASE3_DESIGN.md](doc/PHASE3_DESIGN.md) ⭐

---

### 📅 Phase 4+（未来规划）

- Phase 4: 任务依赖 DAG + 容错机制
- Phase 5: 跨机器分布式 + GPU 支持
- Phase 6: Ray Train/Serve（分布式训练和模型服务）

---

## 📚 文档导航

### 快速开始
- **[README.md](README.md)** - 本文件（项目主页）
- **[examples/README.md](examples/README.md)** - 示例说明

### 核心设计文档
- **[doc/DESIGN.md](doc/DESIGN.md)** - 系统架构和设计理念
- **[doc/PROJECT_STRUCTURE.md](doc/PROJECT_STRUCTURE.md)** - 项目结构详解
- **[doc/CMAKE_GUIDE.md](doc/CMAKE_GUIDE.md)** - CMake 构建系统详解

### 开发阶段文档
1. **[doc/PHASE1_SUMMARY.md](doc/PHASE1_SUMMARY.md)** - Phase 1: 对象存储
2. **[doc/PHASE2_GUIDE.md](doc/PHASE2_GUIDE.md)** - Phase 2: 任务调度
3. **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - Phase 2.5: 代码重构
4. **[doc/PHASE3_DESIGN.md](doc/PHASE3_DESIGN.md)** - Phase 3: 设计文档 ⭐

### 推荐阅读顺序

#### 🔰 新手入门
```
README.md → examples/ → doc/PROJECT_STRUCTURE.md → doc/DESIGN.md
```

#### 📖 深入学习
```
doc/PHASE1_SUMMARY.md → doc/PHASE2_GUIDE.md →
REFACTORING_SUMMARY.md → doc/PHASE3_DESIGN.md
```

#### 👨‍💻 参与开发
```
doc/PHASE3_DESIGN.md → doc/CMAKE_GUIDE.md →
cpp/include/miniray/ (阅读源码注释)
```

---

## 🛠️ 开发指南

### 修改 C++ 代码后重新编译

```bash
# 清理旧构建
rm -rf build/ python/miniray/_miniray_core.*.so

# 重新构建
pip install -e .

# 运行测试
pytest tests/ -v
```

### 调试 C++ 代码

```bash
# Debug 模式构建
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Debug ..
cmake --build .

# 使用 GDB/LLDB 调试
gdb --args python3 -m pytest tests/test_object_store.py
```

### 添加新的 C++ 类

1. 在 `cpp/include/miniray/` 创建头文件
2. 在 `cpp/src/` 创建实现文件
3. 在 `cpp/CMakeLists.txt` 添加源文件
4. 在 `cpp/src/python_bindings.cpp` 添加 pybind11 绑定
5. 重新编译：`pip install -e .`

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_object_store.py -v

# 查看覆盖率
pytest tests/ --cov=miniray --cov-report=html

# 运行示例
python examples/01_object_store.py
```

---

## 🧪 测试

### 测试覆盖

| 模块 | 测试文件 | 测试数 | 状态 |
|------|---------|-------|------|
| ObjectStore | `tests/test_object_store.py` | 8 | ✅ 通过 |
| Scheduler | `tests/test_scheduler.py` | 6 | ✅ 通过 |
| **总计** | | **14** | **✅ 100%** |

### 运行测试

```bash
# 所有测试
pytest tests/ -v

# 对象存储测试
pytest tests/test_object_store.py::TestObjectStore -v

# 调度器测试
pytest tests/test_scheduler.py::TestScheduler -v
```

---

## 📝 常见问题

### Q: 构建失败，找不到 pybind11？

```bash
# 确保安装了 pybind11
pip install pybind11

# 或使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install pybind11 setuptools
```

### Q: import miniray 失败？

确保：
1. 已成功构建：`pip install -e .`
2. 检查 `python/miniray/_miniray_core.*.so` 是否存在
3. 虚拟环境已激活（如果使用）

### Q: 测试失败？

```bash
# 清理并重新构建
rm -rf build/ python/miniray/_miniray_core.*.so
pip install -e .

# 清理共享内存
python -c "import miniray._miniray_core as c; c.cleanup_shared_memory()"

# 重新运行测试
pytest tests/ -v
```

### Q: macOS 出现 "dynamic_lookup" 警告？

这是正常的，不影响功能，可以忽略。

### Q: 如何查看 C++ 代码的详细注释？

所有 C++ 头文件都包含详细的设计文档级注释：
- `cpp/include/miniray/common/memory.h` - 共享内存设计
- `cpp/include/miniray/object_store/object_store.h` - 对象存储设计
- `cpp/include/miniray/raylet/scheduler.h` - 调度器设计
- `cpp/include/miniray/core_worker/core_worker.h` - CoreWorker 设计

---

## 🎓 学习资源

### Ray 相关

- **[Ray 官方文档](https://docs.ray.io/)** - Ray 完整文档
- **[Ray 架构论文](https://arxiv.org/abs/1712.05889)** - Ray 设计理念
- **[Ray GitHub](https://github.com/ray-project/ray)** - Ray 源代码

### 技术栈

- **[pybind11 文档](https://pybind11.readthedocs.io/)** - Python/C++ 绑定
- **[CMake 教程](https://cmake.org/cmake/help/latest/guide/tutorial/)** - CMake 构建系统
- **[C++17 特性](https://en.cppreference.com/w/cpp/17)** - C++ 17 参考

### 推荐阅读

- **分布式系统**：《Designing Data-Intensive Applications》
- **C++ 最佳实践**：《Effective Modern C++》
- **Python 性能优化**：《High Performance Python》

# Mini-Ray 项目结构说明

这个文档详细说明了 Mini-Ray 项目的目录组织和文件用途。

## 📂 完整目录树

```
mini-ray/                           # 项目根目录
├── README.md                       # 项目主文档（快速开始指南）
├── PROJECT_STRUCTURE.md            # 本文件（项目结构详解）
├── .gitignore                      # Git 忽略配置
├── setup.py                        # Python 包安装和 C++ 构建配置
├── CMakeLists.txt                  # CMake 顶层配置
│
├── doc/                            # 📚 文档目录
│   ├── DESIGN.md                   # 系统架构设计文档（核心）
│   ├── IMPORT_GUIDE.md             # 模块导入机制说明
│   ├── TROUBLESHOOTING.md          # 常见问题排查
│   └── GIT_GUIDE.md                # Git 使用指南
│
├── cpp/                            # 🔧 C++ 核心代码
│   ├── CMakeLists.txt              # C++ 构建配置
│   ├── include/                    # C++ 头文件
│   │   └── miniray/
│   │       ├── common/
│   │       │   ├── id.h            # ObjectID, TaskID 等 ID 类
│   │       │   └── object_ref.h    # ObjectRef（Future 引用）
│   │       ├── object_store/
│   │       │   └── object_store.h  # ObjectStore 核心
│   │       ├── scheduler/
│   │       │   └── scheduler.h     # 任务调度器
│   │       └── core_worker/
│   │           └── core_worker.h   # Worker 核心组件
│   └── src/                        # C++ 实现文件
│       ├── common/
│       │   ├── id.cpp
│       │   └── object_ref.cpp
│       ├── object_store/
│       │   └── object_store.cpp
│       ├── scheduler/
│       │   └── scheduler.cpp
│       ├── core_worker/
│       │   └── core_worker.cpp
│       └── python_bindings.cpp     # pybind11 Python 绑定
│
├── python/                         # 🐍 Python 包目录
│   └── miniray/                    # miniray 包
│       ├── __init__.py             # 包入口（导入和导出 API）
│       ├── _miniray_core.so        # C++ 编译生成的扩展模块（.gitignore）
│       ├── api.py                  # Python API 层（init, get, remote 等）
│       ├── actor.py                # Actor 实现
│       ├── scheduler.py            # 调度器 Python 封装
│       └── core.py                 # 纯 Python 实现（备用）
│
├── examples/                       # 📖 示例代码
│   ├── 01_phase1_object_store.py   # Phase 1: ObjectStore 使用示例
│   ├── 02_actor.py                 # Phase 2: Actor 使用示例
│   └── 03_mapreduce.py             # Phase 3: MapReduce 示例
│
├── tests/                          # 🧪 单元测试（pytest）
│   ├── README.md                   # 测试说明文档
│   ├── conftest.py                 # pytest 配置和 fixtures
│   ├── test_object_store.py        # ObjectStore 功能测试
│   ├── test_bindings.py            # pybind11 绑定测试
│   └── test_cpp_core.py            # 旧版测试（手动运行）
│
├── test_phase1.py                  # ✅ Phase 1 验收测试（项目根目录）
│
├── build/                          # 🔨 CMake 构建临时文件（.gitignore）
│   └── temp.xxx/                   # 编译中间文件
│
└── venv/                           # 🐍 Python 虚拟环境（.gitignore）
    └── ...
```

## 🎯 核心目录详解

### 1. **`cpp/` - C++ 核心实现**

这是项目的核心，所有高性能组件都用 C++ 实现。

#### 1.1 `cpp/include/miniray/` - 头文件

```
cpp/include/miniray/
├── common/              # 通用组件
│   ├── id.h            # ID 类型：ObjectID, TaskID, FunctionID
│   └── object_ref.h    # ObjectRef（类似 Future）
│
├── object_store/        # 对象存储
│   └── object_store.h  # 线程安全的对象存储
│
├── scheduler/           # 任务调度
│   └── scheduler.h     # 调度器（Phase 2）
│
└── core_worker/         # Worker 核心
    └── core_worker.h   # Worker 组件（Phase 2）
```

**关键类说明**：

- **ObjectID**: 128-bit UUID，唯一标识对象
- **ObjectRef**: 对象引用，封装 ObjectID，实现 Future 模式
- **ObjectStore**: 核心存储，使用 `std::unordered_map` + `std::mutex`

#### 1.2 `cpp/src/` - 实现文件

```
cpp/src/
├── common/
│   ├── id.cpp              # ID 生成和转换
│   └── object_ref.cpp      # ObjectRef 实现
│
├── object_store/
│   └── object_store.cpp    # ObjectStore 实现
│
└── python_bindings.cpp     # ⭐ pybind11 绑定（重要）
```

**python_bindings.cpp** 是连接 C++ 和 Python 的桥梁：

```cpp
PYBIND11_MODULE(_miniray_core, m) {
    py::class_<ObjectStore>(m, "ObjectStore")
        .def(py::init<>())
        .def("put", ...)
        .def("get", ...)
        .def("delete", ...)
        .def("contains", ...)
        .def("size", ...);
}
```

### 2. **`python/miniray/` - Python 包**

这是用户直接使用的 Python API 层。

```
python/miniray/
├── __init__.py          # 包入口，导入并导出 API
├── _miniray_core.so     # C++ 编译生成（不提交到 git）
├── api.py               # 高层 API：init(), get(), remote()
├── actor.py             # Actor 类和装饰器
├── scheduler.py         # 调度器 Python 封装
└── core.py              # 纯 Python 备用实现
```

#### 2.1 导入层次

```python
# 用户代码
import miniray           # 导入包

# miniray/__init__.py
from . import _miniray_core           # 导入 C++ 模块
from .api import init, get, remote    # 导入 Python API

# 用户可以这样使用
miniray.init()
ref = miniray.remote(func).remote(arg)
result = miniray.get(ref)
```

#### 2.2 文件职责

| 文件 | 职责 | 依赖 |
|------|------|------|
| `__init__.py` | 包入口，统一导出接口 | `_miniray_core`, `api.py` |
| `_miniray_core.so` | C++ 核心功能 | C++ 编译生成 |
| `api.py` | 高层 API 封装 | `_miniray_core` |
| `actor.py` | Actor 模式实现 | `_miniray_core`, `api.py` |
| `scheduler.py` | 调度器 Python 接口 | `_miniray_core` |
| `core.py` | 纯 Python 备用实现 | 无（独立） |

### 3. **`examples/` - 示例代码**

**目的**：展示如何使用 mini-ray 的各种功能

```
examples/
├── 01_phase1_object_store.py   # Phase 1 示例
│   ├── 基础 put/get
│   ├── Python 对象序列化
│   ├── 批量操作
│   ├── 生命周期管理
│   └── 真实场景模拟
│
├── 02_actor.py                 # Phase 2: Actor 示例
└── 03_mapreduce.py             # Phase 3: MapReduce 示例
```

**运行方式**：
```bash
python3 examples/01_phase1_object_store.py
```

**特点**：
- ✅ 可直接运行（包含 sys.path 设置）
- ✅ 包含详细注释
- ✅ 演示真实使用场景
- ✅ 按 Phase 组织

### 4. **`tests/` - 单元测试**

**目的**：自动化测试，确保代码正确性

```
tests/
├── README.md                # 测试文档（如何运行、编写测试）
├── conftest.py              # pytest 配置和 fixtures
├── test_object_store.py     # ObjectStore 测试（5 个测试类）
├── test_bindings.py         # pybind11 绑定测试
└── test_cpp_core.py         # 旧版测试（保留）
```

**运行方式**：
```bash
pytest tests/                 # 运行所有测试
pytest tests/ -v              # 详细输出
pytest tests/ -k "put"        # 只运行包含 "put" 的测试
```

**测试组织**（以 `test_object_store.py` 为例）：
```python
class TestObjectStoreBasic:           # 基础功能
class TestObjectStorePythonObjects:   # Python 对象
class TestObjectStoreBatch:           # 批量操作
class TestObjectStoreEdgeCases:       # 边界情况
class TestObjectStoreIntegration:     # 集成测试
```

### 5. **`doc/` - 文档目录**

```
doc/
├── DESIGN.md              # 系统架构设计（最重要）
├── IMPORT_GUIDE.md        # 模块导入机制说明
├── TROUBLESHOOTING.md     # 常见问题
└── GIT_GUIDE.md           # Git 使用指南
```

**必读文档**：
1. **DESIGN.md** - 理解整体架构和分层设计
2. **IMPORT_GUIDE.md** - 理解为什么 import 要这样写

## 🔄 构建流程

### 完整构建流程图

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 用户执行：python3 setup.py build_ext --inplace          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. setuptools 加载 setup.py                                 │
│    - 读取配置                                                │
│    - 发现 ext_modules=[CMakeExtension('_miniray_core')]    │
│    - 使用 cmdclass={'build_ext': CMakeBuild}               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. CMakeBuild.run() 开始执行                                │
│    - 检查 CMake 是否安装                                     │
│    - 调用 build_extension(ext) 对每个扩展                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. CMakeBuild.build_extension()                             │
│    - 准备 CMake 参数                                         │
│    - 创建 build/ 临时目录                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 运行 CMake 配置                                           │
│    cmake <source_dir> \                                     │
│      -DCMAKE_LIBRARY_OUTPUT_DIRECTORY=python/miniray/ \     │
│      -DPYTHON_EXECUTABLE=/usr/bin/python3 \                 │
│      -DCMAKE_BUILD_TYPE=Release                             │
│                                                              │
│    - 读取 CMakeLists.txt                                    │
│    - 查找 pybind11                                          │
│    - 生成 Makefile 或 Ninja 文件                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. 运行 CMake 构建                                           │
│    cmake --build . --config Release -j4                     │
│                                                              │
│    - 调用底层编译器（g++/clang++）                          │
│    - 编译所有 .cpp 文件                                      │
│    - 链接生成 _miniray_core.so                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. 输出文件生成                                              │
│    python/miniray/_miniray_core.so（macOS/Linux）           │
│    python/miniray/_miniray_core.pyd（Windows）              │
└─────────────────────────────────────────────────────────────┘
```

### CMake 文件层次

```
CMakeLists.txt（根目录）
    ├── project(miniray)
    ├── find_package(pybind11)
    └── add_subdirectory(cpp)
            │
            ▼
        cpp/CMakeLists.txt
            ├── file(GLOB_RECURSE MINIRAY_SOURCES ...)
            ├── pybind11_add_module(_miniray_core ...)
            └── set_target_properties(OUTPUT_NAME "_miniray_core")
```

## 📝 文件命名约定

### C++ 文件
- **头文件**：`*.h`（全部小写，下划线分隔）
  - `object_store.h`
  - `object_ref.h`
  - `id.h`

- **实现文件**：`*.cpp`
  - `object_store.cpp`
  - `python_bindings.cpp`

- **命名空间**：`miniray::xxx`
  ```cpp
  namespace miniray {
  namespace object_store {
      class ObjectStore { ... };
  }
  }
  ```

### Python 文件
- **包/模块**：全部小写，下划线分隔
  - `miniray/`
  - `api.py`
  - `actor.py`

- **测试文件**：`test_*.py`
  - `test_object_store.py`
  - `test_bindings.py`

- **示例文件**：`数字_phase_功能.py`
  - `01_phase1_object_store.py`
  - `02_actor.py`

### 验收测试
- **位置**：项目根目录
- **命名**：`test_phaseN.py`
  - `test_phase1.py`
  - `test_phase2.py`（未来）

## 🔍 查找代码的技巧

### 按功能查找

| 功能 | 位置 |
|------|------|
| ObjectStore 实现 | `cpp/src/object_store/object_store.cpp` |
| ObjectStore 头文件 | `cpp/include/miniray/object_store/object_store.h` |
| Python 绑定 | `cpp/src/python_bindings.cpp` |
| Python API | `python/miniray/api.py` |
| 测试 ObjectStore | `tests/test_object_store.py` |
| ObjectStore 示例 | `examples/01_phase1_object_store.py` |

### 按问题查找

| 问题 | 查找位置 |
|------|----------|
| 编译错误 | `cpp/CMakeLists.txt`, `setup.py` |
| 导入错误 | `python/miniray/__init__.py`, `doc/IMPORT_GUIDE.md` |
| 运行时错误 | `cpp/src/python_bindings.cpp` |
| 测试失败 | `tests/` |
| IDE 配置问题 | `doc/TROUBLESHOOTING.md` |

## 🚀 常用操作速查

### 构建和测试
```bash
# 构建 C++ 扩展
python3 setup.py build_ext --inplace

# 运行验收测试
python3 test_phase1.py

# 运行单元测试
pytest tests/ -v

# 运行示例
python3 examples/01_phase1_object_store.py
```

### 清理
```bash
# 清理构建文件
rm -rf build/

# 清理编译生成的扩展
rm -f python/miniray/_miniray_core*.so
rm -f python/miniray/_miniray_core*.dylib

# 清理 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### 开发流程
```bash
# 1. 修改 C++ 代码
vim cpp/src/object_store/object_store.cpp

# 2. 重新编译
python3 setup.py build_ext --inplace

# 3. 运行测试验证
pytest tests/test_object_store.py -v

# 4. 运行示例验证
python3 examples/01_phase1_object_store.py
```

## 📊 文件依赖关系

### C++ 层依赖
```
python_bindings.cpp
    ├── #include "miniray/object_store/object_store.h"
    ├── #include "miniray/common/object_ref.h"
    └── #include "miniray/common/id.h"

object_store.cpp
    ├── #include "miniray/object_store/object_store.h"
    └── #include "miniray/common/object_ref.h"

object_ref.cpp
    └── #include "miniray/common/object_ref.h"
```

### Python 层依赖
```
用户代码
    └── import miniray

miniray/__init__.py
    ├── from . import _miniray_core
    └── from .api import init, get, remote

miniray/api.py
    └── from . import _miniray_core

tests/test_object_store.py
    └── import _miniray_core (通过 conftest.py)

examples/01_phase1_object_store.py
    └── import _miniray_core (直接导入)
```

## 🎓 学习路径建议

### 1. 理解架构（1-2 小时）
1. 阅读 `doc/DESIGN.md` - 理解整体设计
2. 阅读本文档 - 理解文件组织
3. 查看 `cpp/include/miniray/` - 理解 C++ 接口

### 2. 运行示例（30 分钟）
1. 构建项目：`python3 setup.py build_ext --inplace`
2. 运行示例：`python3 examples/01_phase1_object_store.py`
3. 运行测试：`pytest tests/ -v`

### 3. 阅读代码（2-3 小时）
1. `cpp/include/miniray/common/id.h` - 理解 ID 设计
2. `cpp/src/object_store/object_store.cpp` - 理解存储实现
3. `cpp/src/python_bindings.cpp` - 理解 Python 绑定
4. `python/miniray/__init__.py` - 理解 Python 层组织

### 4. 修改代码（1-2 小时）
1. 在 `ObjectStore` 添加一个新方法（如 `list_all_refs()`）
2. 在 `python_bindings.cpp` 暴露这个方法
3. 重新编译并测试
4. 在 `tests/test_object_store.py` 添加测试

### 5. 实现新功能（Phase 2）
1. 阅读 `doc/DESIGN.md` 的 Phase 2 部分
2. 实现 `Scheduler` 类
3. 实现 `CoreWorker` 类
4. 添加测试和示例

## 📚 相关文档

- [README.md](../README.md) - 项目介绍和快速开始
- [doc/DESIGN.md](DESIGN.md) - 系统架构设计
- [doc/IMPORT_GUIDE.md](doc/IMPORT_GUIDE.md) - 模块导入说明
- [tests/README.md](../tests/README.md) - 测试说明
- [doc/TROUBLESHOOTING.md](doc/TROUBLESHOOTING.md) - 问题排查

## ❓ 常见问题

### Q1: 为什么 Python 代码在 `python/miniray/` 而不是 `miniray/`？
**A**: 这是为了避免导入混淆：
- `python/` 目录表明这是 Python 相关代码
- `miniray/` 是实际的包名
- 编译生成的 `.so` 文件也在 `python/miniray/` 下

### Q2: 为什么测试文件要 `import _miniray_core` 而不是 `from miniray import ...`？
**A**: 为了避免循环导入问题，详见 [doc/IMPORT_GUIDE.md](doc/IMPORT_GUIDE.md)

### Q3: `test_phase1.py` 和 `tests/` 有什么区别？
**A**:
- `test_phase1.py` 是**验收测试**，验证整个 Phase 的功能
- `tests/` 是**单元测试**，验证每个组件的具体功能

### Q4: `examples/` 和 `tests/` 的代码能合并吗？
**A**: 不建议：
- `examples/` 是教学代码，注重可读性和完整性
- `tests/` 是测试代码，注重覆盖率和自动化
- 两者目的不同，应该分开

### Q5: 修改 C++ 代码后需要重启 Python 吗？
**A**: 需要：
1. 重新编译：`python3 setup.py build_ext --inplace`
2. 重启 Python 解释器（或重新导入模块）
3. `.so` 文件加载后会被缓存，必须重启

---

**维护者**：Mini-Ray Contributors
**最后更新**：2025-12-05

如有问题，请查阅 [doc/TROUBLESHOOTING.md](doc/TROUBLESHOOTING.md) 或提交 Issue。

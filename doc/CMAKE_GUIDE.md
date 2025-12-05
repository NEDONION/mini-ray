# CMake 构建系统详解

## ❓ 为什么有两个 CMakeLists.txt？

Mini-Ray 项目有两个 CMakeLists.txt 文件：

```
mini-ray/
├── CMakeLists.txt           # 根 CMakeLists.txt（顶层配置）
└── cpp/
    └── CMakeLists.txt       # C++ 子项目 CMakeLists.txt（具体构建）
```

**简单回答**：
- **根 CMakeLists.txt**：项目的**总管**，负责全局设置和协调
- **cpp/CMakeLists.txt**：C++ 代码的**执行者**，负责实际编译

这是 CMake **分层构建**的标准做法，类似于公司的管理层级：
- 根 CMakeLists.txt = CEO（制定战略、设置标准）
- cpp/CMakeLists.txt = 部门经理（执行具体任务）

---

## 📊 两个文件的职责对比

| 特性 | 根 CMakeLists.txt | cpp/CMakeLists.txt |
|------|------------------|-------------------|
| **位置** | `mini-ray/CMakeLists.txt` | `mini-ray/cpp/CMakeLists.txt` |
| **作用域** | 整个项目 | C++ 子项目 |
| **主要职责** | 全局配置、查找依赖 | 编译 C++ 代码 |
| **包含子项目** | ✅（通过 `add_subdirectory`） | ❌ |
| **定义编译选项** | ✅（全局编译器标志） | ❌ |
| **查找 pybind11** | ✅ | ❌（继承自根） |
| **编译目标** | ❌ | ✅（`pybind11_add_module`） |
| **设置输出路径** | ✅（全局默认） | ✅（覆盖特定路径） |

---

## 📝 根 CMakeLists.txt 详解

**位置**：`mini-ray/CMakeLists.txt`

### 完整代码（带注释）

```cmake
# ============================================================
# 第一部分：项目基本信息
# ============================================================

# CMake 最低版本要求
# 3.15 引入了许多有用的功能，如 CMAKE_CROSSCOMPILING_EMULATOR
cmake_minimum_required(VERSION 3.15)

# 定义项目
# - 项目名称：miniray
# - 版本：0.1.0
# - 语言：C++（不包括 C、Fortran 等）
project(miniray VERSION 0.1.0 LANGUAGES CXX)

# ============================================================
# 第二部分：C++ 标准设置
# ============================================================

# 设置 C++ 标准为 C++17
# C++17 提供了很多现代特性：结构化绑定、if constexpr、std::optional 等
set(CMAKE_CXX_STANDARD 17)

# 要求必须使用 C++17（如果编译器不支持则报错）
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 禁用编译器扩展（使用标准 C++，不使用 GNU 扩展等）
# 这确保代码的可移植性
set(CMAKE_CXX_EXTENSIONS OFF)

# ============================================================
# 第三部分：编译选项
# ============================================================

# 通用编译选项（Debug 和 Release 都使用）
# -Wall: 启用所有警告
# -Wextra: 启用额外警告
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra")

# Debug 模式编译选项
# -g: 包含调试信息（可以用 gdb/lldb 调试）
# -O0: 不优化（编译快，方便调试）
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g -O0")

# Release 模式编译选项
# -O3: 最高优化级别（性能最好，但编译慢）
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3")

# ============================================================
# 第四部分：输出目录设置
# ============================================================

# 设置默认输出目录（如果子项目不覆盖）
# 静态库输出目录（.a 文件）
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# 动态库输出目录（.so/.dylib 文件）
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# 可执行文件输出目录
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# ============================================================
# 第五部分：查找依赖 - pybind11
# ============================================================

# 尝试查找 pybind11（通过 CMake 的 find_package）
# CONFIG 模式：查找 pybind11Config.cmake 文件
find_package(pybind11 CONFIG)

# 如果没找到，尝试使用 pip 安装的版本
if(NOT pybind11_FOUND)
    message(STATUS "pybind11 not found, will try to use pip installed version")

    # 执行 Python 命令获取 pybind11 的 CMake 目录
    execute_process(
        COMMAND python3 -m pybind11 --cmakedir
        OUTPUT_VARIABLE pybind11_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )

    # 如果找到了路径，再次尝试查找
    if(pybind11_DIR)
        message(STATUS "Found pybind11 via pip: ${pybind11_DIR}")
        find_package(pybind11 CONFIG PATHS ${pybind11_DIR})
    endif()
endif()

# 如果还是没找到，报错退出
if(NOT pybind11_FOUND)
    message(FATAL_ERROR "pybind11 not found. Please install via: pip install pybind11")
endif()

# ============================================================
# 第六部分：添加子目录（最重要！）
# ============================================================

# 添加 cpp/ 子目录
# CMake 会自动查找 cpp/CMakeLists.txt 并执行
# 这是连接根 CMakeLists.txt 和 cpp/CMakeLists.txt 的关键
add_subdirectory(cpp)
```

### 关键点说明

1. **`add_subdirectory(cpp)`** - 这是最关键的一行！
   - 告诉 CMake：去 `cpp/` 目录找 CMakeLists.txt
   - `cpp/CMakeLists.txt` 会继承根配置（C++ 标准、编译选项等）
   - 形成了分层的构建系统

2. **查找 pybind11 的两种方式**
   - 方式1：系统安装的 pybind11（`find_package(pybind11 CONFIG)`）
   - 方式2：pip 安装的 pybind11（`python3 -m pybind11 --cmakedir`）

3. **编译选项的继承**
   - 在根设置的 `CMAKE_CXX_STANDARD` 会被 `cpp/` 继承
   - 子项目不需要重复设置

---

## 📝 cpp/CMakeLists.txt 详解

**位置**：`mini-ray/cpp/CMakeLists.txt`

### 完整代码（带注释）

```cmake
# ============================================================
# 第一部分：头文件目录
# ============================================================

# 包含头文件目录
# CMAKE_CURRENT_SOURCE_DIR = mini-ray/cpp/
# 所以这里添加的是 mini-ray/cpp/include/
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# 这样 C++ 代码就可以：
# #include "miniray/common/id.h"
# 而不是：
# #include "cpp/include/miniray/common/id.h"

# ============================================================
# 第二部分：收集源文件
# ============================================================

# 定义源文件列表
set(MINIRAY_SOURCES
    src/python_bindings.cpp
)

# 为什么不用 GLOB？
# file(GLOB MINIRAY_SOURCES "src/*.cpp")  # 不推荐
#
# 原因：
# 1. GLOB 在添加新文件后不会自动重新配置
# 2. 手动列出更清晰、可控
# 3. 对于大项目，GLOB 可能包含不需要的文件

# ============================================================
# 第三部分：创建 Python 扩展模块（核心！）
# ============================================================

# 使用 pybind11 提供的函数创建 Python 模块
# pybind11_add_module 是一个特殊的 CMake 函数，由 pybind11 提供
#
# 参数说明：
#   - _miniray_core: 模块名称（必须与 PYBIND11_MODULE 中的名称一致）
#   - ${MINIRAY_SOURCES}: 源文件列表
pybind11_add_module(_miniray_core ${MINIRAY_SOURCES})

# pybind11_add_module 做了什么？
# 1. 创建一个 shared library（.so/.dylib）
# 2. 链接 Python 库
# 3. 设置正确的编译标志（-fPIC 等）
# 4. 处理 Python 和 C++ 之间的 ABI 兼容性

# ============================================================
# 第四部分：设置输出属性（覆盖根设置）
# ============================================================

# 设置目标属性
set_target_properties(_miniray_core PROPERTIES
    # PREFIX "": 移除默认的 "lib" 前缀
    # 默认：lib_miniray_core.so
    # 设置后：_miniray_core.so
    PREFIX ""

    # OUTPUT_NAME: 输出文件名
    OUTPUT_NAME "_miniray_core"

    # LIBRARY_OUTPUT_DIRECTORY: 输出目录（覆盖根设置）
    # CMAKE_SOURCE_DIR = mini-ray/ (项目根目录)
    # 所以输出到：mini-ray/python/miniray/
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/python/miniray
)

# 为什么输出到 python/miniray/？
# 因为这是 Python 包的位置，Python 可以直接导入：
#   import sys
#   sys.path.append('python/miniray')
#   import _miniray_core

# ============================================================
# 第五部分：macOS 特殊处理
# ============================================================

# 如果是 macOS，设置 rpath
if(APPLE)
    set_target_properties(_miniray_core PROPERTIES
        # @loader_path: 相对于加载器的路径
        # 这样动态库可以找到依赖的其他库
        INSTALL_RPATH "@loader_path"

        # 构建时就使用 install rpath
        BUILD_WITH_INSTALL_RPATH TRUE
    )
endif()

# rpath 是什么？
# Runtime Path：动态链接器搜索共享库的路径
# macOS 使用 @loader_path，Linux 使用 $ORIGIN

# ============================================================
# 第六部分：链接依赖库
# ============================================================

# 查找线程库（std::thread 需要）
find_package(Threads REQUIRED)

# 链接线程库
# PRIVATE: 只有 _miniray_core 使用，不传递给依赖它的其他目标
target_link_libraries(_miniray_core PRIVATE Threads::Threads)

# 为什么需要线程库？
# ObjectStore 使用 std::mutex，需要链接 pthread（Linux）
```

### 关键点说明

1. **`pybind11_add_module`** - 最核心的函数
   - 这是 pybind11 提供的特殊函数
   - 自动处理 Python 扩展的所有复杂配置
   - 比手动写 `add_library` 简单很多

2. **输出路径的覆盖**
   - 根 CMakeLists.txt 设置默认输出到 `build/lib/`
   - cpp/CMakeLists.txt 覆盖为 `python/miniray/`
   - 这样生成的 `.so` 文件直接在 Python 包里

3. **`set_target_properties` 的 PREFIX ""**
   - 默认情况下，库文件会有 `lib` 前缀
   - Python 扩展模块不需要这个前缀
   - 所以要显式设置为空

---

## 🔄 构建流程（从执行到生成）

### 完整流程图

```
用户执行：python3 setup.py build_ext --inplace
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ setup.py 的 CMakeBuild 类开始执行                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ CMake 配置阶段：cmake <source_dir> [args]               │
│                                                          │
│ 1. 读取根 CMakeLists.txt                                │
│    - 设置项目名称和版本                                  │
│    - 设置 C++ 标准为 17                                  │
│    - 设置编译选项（-Wall -Wextra -O3）                  │
│    - 查找 pybind11                                       │
│    - 执行 add_subdirectory(cpp)  ← 关键！               │
│                                                          │
│ 2. 进入 cpp/ 子目录                                     │
│    - 读取 cpp/CMakeLists.txt                            │
│    - 设置头文件路径（cpp/include/）                     │
│    - 收集源文件（python_bindings.cpp）                  │
│    - 调用 pybind11_add_module(_miniray_core ...)        │
│    - 设置输出路径为 python/miniray/                     │
│    - 链接线程库                                          │
│                                                          │
│ 3. 生成构建文件（Makefile 或 Ninja）                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ CMake 构建阶段：cmake --build . [args]                  │
│                                                          │
│ 1. 调用底层编译器（g++/clang++）                        │
│    编译命令示例：                                        │
│    c++ -O3 -std=c++17 -Wall -Wextra -fPIC \             │
│        -I cpp/include/ \                                 │
│        -I /usr/include/python3.x/ \                      │
│        -c cpp/src/python_bindings.cpp \                  │
│        -o build/temp/python_bindings.o                   │
│                                                          │
│ 2. 链接生成共享库                                        │
│    链接命令示例：                                        │
│    c++ -shared \                                         │
│        build/temp/python_bindings.o \                    │
│        -lpthread \                                       │
│        -o python/miniray/_miniray_core.so                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 完成：生成 python/miniray/_miniray_core.so              │
└─────────────────────────────────────────────────────────┘
```

### add_subdirectory 的作用

```
根 CMakeLists.txt
    │
    │ add_subdirectory(cpp)
    │
    ▼
cpp/CMakeLists.txt
    │
    │ 继承：
    │  - CMAKE_CXX_STANDARD = 17
    │  - CMAKE_CXX_FLAGS = -Wall -Wextra
    │  - pybind11 查找结果
    │
    │ 自己的任务：
    │  - 编译 python_bindings.cpp
    │  - 生成 _miniray_core.so
    │  - 输出到 python/miniray/
```

---

## 🎯 为什么需要分层？

### 好处1：职责分离

```
根 CMakeLists.txt：
  ✅ 全局策略（C++ 标准、编译器选项）
  ✅ 依赖查找（pybind11、Threads）
  ✅ 项目组织（子目录管理）

cpp/CMakeLists.txt：
  ✅ 具体实现（编译哪些文件）
  ✅ 目标配置（输出路径、链接库）
  ✅ 平台特殊处理（macOS rpath）
```

### 好处2：可扩展性

如果未来添加更多子项目：

```
mini-ray/
├── CMakeLists.txt           # 根配置（不变）
├── cpp/
│   └── CMakeLists.txt       # C++ 核心
├── python/
│   └── CMakeLists.txt       # Python 包（可选）
└── tests/
    └── CMakeLists.txt       # C++ 单元测试（可选）
```

根 CMakeLists.txt 只需要添加：
```cmake
add_subdirectory(cpp)
add_subdirectory(tests)
```

### 好处3：配置继承

```
根设置 C++17
    ↓
cpp/ 自动继承 C++17
tests/ 自动继承 C++17
```

不需要在每个子项目重复设置。

---

## 🆚 对比：单个 vs 多个 CMakeLists.txt

### 如果只有一个 CMakeLists.txt（不推荐）

```cmake
# mini-ray/CMakeLists.txt（臃肿版）

cmake_minimum_required(VERSION 3.15)
project(miniray)

# C++ 标准
set(CMAKE_CXX_STANDARD 17)
# ... 更多全局设置 ...

# 查找 pybind11
find_package(pybind11)

# 包含目录
include_directories(cpp/include)

# 源文件
set(MINIRAY_SOURCES
    cpp/src/python_bindings.cpp
    cpp/src/common/id.cpp
    cpp/src/object_store/object_store.cpp
    # ... 更多文件 ...
)

# 创建模块
pybind11_add_module(_miniray_core ${MINIRAY_SOURCES})

# 设置属性
set_target_properties(_miniray_core PROPERTIES ...)

# macOS 处理
if(APPLE) ...

# 链接库
target_link_libraries(...)
```

**问题**：
- ❌ 所有配置混在一起，难以维护
- ❌ C++ 相关的配置和项目全局配置混淆
- ❌ 添加新子项目时需要修改根文件
- ❌ 不符合 CMake 最佳实践

### 使用两个 CMakeLists.txt（推荐 ✅）

```cmake
# mini-ray/CMakeLists.txt（清晰版）
cmake_minimum_required(VERSION 3.15)
project(miniray)
set(CMAKE_CXX_STANDARD 17)
find_package(pybind11)
add_subdirectory(cpp)  # 就这么简单！
```

```cmake
# mini-ray/cpp/CMakeLists.txt（专注版）
include_directories(include)
set(MINIRAY_SOURCES src/python_bindings.cpp)
pybind11_add_module(_miniray_core ${MINIRAY_SOURCES})
set_target_properties(_miniray_core PROPERTIES ...)
```

**优点**：
- ✅ 清晰分离全局和局部配置
- ✅ 每个文件只关注自己的职责
- ✅ 易于添加新子项目
- ✅ 符合 CMake 社区标准

---

## 📚 实际项目中的 CMake 分层

许多大型项目都采用这种分层结构：

### LLVM/Clang
```
llvm/
├── CMakeLists.txt         # 根配置
├── lib/
│   └── CMakeLists.txt     # 核心库
├── tools/
│   ├── clang/
│   │   └── CMakeLists.txt # Clang 子项目
│   └── lldb/
│       └── CMakeLists.txt # LLDB 子项目
└── unittests/
    └── CMakeLists.txt     # 测试
```

### TensorFlow
```
tensorflow/
├── CMakeLists.txt         # 根配置
├── core/
│   └── CMakeLists.txt     # 核心库
├── python/
│   └── CMakeLists.txt     # Python 绑定
└── contrib/
    └── CMakeLists.txt     # 扩展
```

### Mini-Ray（我们的项目）
```
mini-ray/
├── CMakeLists.txt         # 根配置
└── cpp/
    └── CMakeLists.txt     # C++ 核心
```

**未来可能扩展为**：
```
mini-ray/
├── CMakeLists.txt
├── cpp/
│   ├── CMakeLists.txt
│   ├── common/
│   │   └── CMakeLists.txt     # 通用组件
│   └── object_store/
│       └── CMakeLists.txt     # 对象存储
└── tests/
    └── CMakeLists.txt         # C++ 单元测试
```

---

## 🔧 常见问题

### Q1: 能不能把所有配置都放在根 CMakeLists.txt？

**A**: 技术上可以，但不推荐：
- ❌ 违反单一职责原则
- ❌ 代码组织混乱
- ❌ 难以维护和扩展
- ✅ 使用 `add_subdirectory` 更清晰

### Q2: cpp/CMakeLists.txt 需要重复设置 C++ 标准吗？

**A**: 不需要！子项目自动继承根配置：
```cmake
# 根 CMakeLists.txt
set(CMAKE_CXX_STANDARD 17)  # 设置一次

# cpp/CMakeLists.txt
# 自动继承 CMAKE_CXX_STANDARD = 17，不需要重复设置
```

### Q3: 如果有多个 C++ 子项目怎么办？

**A**: 每个子项目一个 CMakeLists.txt：
```cmake
# 根 CMakeLists.txt
add_subdirectory(cpp/common)      # 通用库
add_subdirectory(cpp/object_store) # 对象存储
add_subdirectory(cpp/scheduler)    # 调度器
```

### Q4: setup.py 调用的是哪个 CMakeLists.txt？

**A**: setup.py 调用根 CMakeLists.txt，然后根会自动调用子 CMakeLists.txt：
```python
# setup.py
subprocess.check_call(
    ['cmake', str(Path(__file__).parent)] + cmake_args,
    #         ^^^^^^^^^^^^^^^^^^^^^^^^
    #         这是项目根目录，所以调用根 CMakeLists.txt
    cwd=build_temp
)
```

### Q5: 可以有三层甚至更多层吗？

**A**: 当然可以！CMake 支持任意层级：
```
mini-ray/
├── CMakeLists.txt               # 第 1 层
└── cpp/
    ├── CMakeLists.txt           # 第 2 层
    ├── common/
    │   └── CMakeLists.txt       # 第 3 层
    └── object_store/
        └── CMakeLists.txt       # 第 3 层
```

---

## 📖 总结

### 两个 CMakeLists.txt 的角色

| 文件 | 角色 | 类比 |
|------|------|------|
| 根 CMakeLists.txt | 项目总管 | 公司 CEO |
| cpp/CMakeLists.txt | 编译执行者 | 部门经理 |

### 关键连接

```cmake
# 根 CMakeLists.txt 的最后一行：
add_subdirectory(cpp)
```

这一行是连接两个文件的桥梁！

### 记住三点

1. **分层是为了清晰** - 不同职责分开管理
2. **配置会继承** - 子项目自动继承根配置
3. **这是标准做法** - 所有大型项目都这么做

---

**参考资料**：
- [CMake 官方文档 - add_subdirectory](https://cmake.org/cmake/help/latest/command/add_subdirectory.html)
- [CMake 最佳实践](https://cliutils.gitlab.io/modern-cmake/)
- [pybind11 CMake 集成](https://pybind11.readthedocs.io/en/stable/compiling.html)

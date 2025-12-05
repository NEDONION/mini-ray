"""
setup.py - Mini-Ray 项目安装配置文件

这个文件的作用：
1. 定义如何构建 C++ 扩展模块（使用 CMake）
2. 配置 Python 包的元数据（名称、版本、依赖等）
3. 提供安装命令：pip install . 或 python setup.py install

核心概念：
- setuptools: Python 的包管理和分发工具
- Extension: 表示一个 C/C++ 扩展模块
- CMake: 跨平台的 C++ 构建系统
- pybind11: 用于创建 Python 和 C++ 的绑定

使用方式：
  开发模式（推荐）：
    python3 setup.py build_ext --inplace

  安装到系统：
    pip install .

  开发安装（可编辑）：
    pip install -e .
"""

import os
import subprocess
import sys
from pathlib import Path

from setuptools import setup, Extension, find_packages
from setuptools.command.build_ext import build_ext


class CMakeExtension(Extension):
    """
    自定义的 Extension 类，用于表示需要用 CMake 构建的 C++ 扩展

    与普通的 Extension 不同，CMakeExtension 不需要指定源文件列表，
    因为源文件的管理由 CMakeLists.txt 负责。

    Args:
        name: 扩展模块的名称，例如 "_miniray_core"
    """
    def __init__(self, name):
        # 调用父类构造函数，sources=[] 表示不指定源文件
        super().__init__(name, sources=[])


class CMakeBuild(build_ext):
    """
    自定义的 build_ext 命令，用于使用 CMake 构建 C++ 扩展

    这个类覆盖了 setuptools 默认的 build_ext 命令，
    使得我们可以使用 CMake 而不是 setuptools 内置的编译器来构建扩展。

    工作流程：
    1. 检查 CMake 是否已安装
    2. 为每个扩展调用 build_extension 方法
    3. build_extension 会运行 CMake 配置和构建命令
    """
    def run(self):
        """
        主入口函数，在构建开始时被调用

        首先检查 CMake 是否可用，然后构建所有扩展。
        """
        # 检查 CMake 是否已安装
        try:
            subprocess.check_output(['cmake', '--version'])
        except OSError:
            raise RuntimeError(
                "CMake must be installed to build the extension\n"
                "Install with: brew install cmake (macOS) or apt-get install cmake (Linux)"
            )

        # 遍历所有扩展并构建
        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        """
        构建单个扩展模块

        这个方法执行两个主要步骤：
        1. 运行 CMake 配置（cmake <source_dir> <args>）
        2. 运行 CMake 构建（cmake --build <build_dir>）

        Args:
            ext: CMakeExtension 实例，表示要构建的扩展
        """
        # 获取扩展模块的输出目录
        # 例如：对于 _miniray_core，这会是 python/miniray/
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))

        # ============================================================
        # 第一步：配置 CMake 参数
        # ============================================================

        # CMake 配置参数（传递给 cmake 命令）
        cmake_args = [
            # 指定生成的 .so/.dylib 文件的输出目录
            # 这确保 _miniray_core.so 生成在 python/miniray/ 目录下
            f'-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}',

            # 告诉 CMake 使用哪个 Python 解释器
            # 这对于 pybind11 找到正确的 Python.h 头文件很重要
            f'-DPYTHON_EXECUTABLE={sys.executable}',

            # 构建类型：Release（优化的，用于生产）
            # 其他选项：Debug（包含调试信息）、RelWithDebInfo（带调试信息的优化版）
            '-DCMAKE_BUILD_TYPE=Release',
        ]

        # ============================================================
        # 第二步：配置构建参数
        # ============================================================

        # 构建参数（传递给 cmake --build 命令）
        build_args = [
            '--config', 'Release'  # 确保使用 Release 配置
        ]

        # 并行构建（加速编译）
        # 如果用户指定了 --parallel N，使用 N 个线程
        # 否则默认使用 4 个线程
        if hasattr(self, 'parallel') and self.parallel:
            build_args += ['-j', str(self.parallel)]
        else:
            build_args += ['-j4']  # 默认 4 线程

        # ============================================================
        # 第三步：创建构建目录
        # ============================================================

        # 创建临时构建目录（通常是 build/temp.xxx）
        # 所有 CMake 生成的中间文件都会放在这里
        build_temp = Path(self.build_temp)
        build_temp.mkdir(parents=True, exist_ok=True)

        # ============================================================
        # 第四步：运行 CMake 配置
        # ============================================================

        # 运行 CMake 配置命令
        # 这会读取 CMakeLists.txt 并生成 Makefile 或其他构建文件
        print(f"Running CMake in {build_temp}")
        print(f"CMake args: {cmake_args}")
        subprocess.check_call(
            ['cmake', str(Path(__file__).parent)] + cmake_args,
            cwd=build_temp
        )

        # ============================================================
        # 第五步：运行 CMake 构建
        # ============================================================

        # 运行实际的编译过程
        # 这会调用底层的编译器（g++/clang++）编译 C++ 代码
        print(f"Building extension {ext.name}")
        print(f"Build args: {build_args}")
        subprocess.check_call(
            ['cmake', '--build', '.'] + build_args,
            cwd=build_temp
        )


# ============================================================
# 读取项目 README（用于 PyPI 等平台的长描述）
# ============================================================
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# ============================================================
# 主配置：setup() 函数
# ============================================================
# 这是整个 setup.py 的核心，定义了包的所有元数据和构建配置
setup(
    # -------------------- 基本信息 --------------------
    # 包名称（用于 pip install <name>）
    name='mini-ray',

    # 版本号（遵循语义化版本 major.minor.patch）
    version='0.1.0',

    # 作者信息
    author='Mini-Ray Contributors',

    # 简短描述（一行）
    description='A simplified Ray implementation for learning distributed systems',

    # 详细描述（从 README.md 读取）
    long_description=long_description,
    long_description_content_type='text/markdown',

    # -------------------- 包配置 --------------------
    # 指定要包含的 Python 包
    # 这里手动指定 'miniray' 而不是使用 find_packages()
    # 因为我们的目录结构比较特殊（python/miniray/）
    packages=['miniray'],

    # 指定包的实际位置
    # 'miniray' 包的代码在 'python/miniray/' 目录下
    package_dir={'miniray': 'python/miniray'},

    # -------------------- C++ 扩展配置 --------------------
    # 声明需要构建的 C++ 扩展模块
    # CMakeExtension 是我们上面定义的自定义类
    ext_modules=[CMakeExtension('_miniray_core')],

    # 自定义构建命令
    # 使用我们的 CMakeBuild 类来替代默认的 build_ext
    cmdclass={'build_ext': CMakeBuild},

    # -------------------- 依赖配置 --------------------
    # 运行时依赖（安装时自动安装）
    install_requires=[
        'pybind11>=2.6.0',  # 用于 Python-C++ 绑定
    ],

    # Python 版本要求
    python_requires='>=3.7',

    # -------------------- PyPI 分类信息 --------------------
    # 用于在 PyPI 上分类和搜索
    classifiers=[
        # 开发状态
        'Development Status :: 3 - Alpha',

        # 目标用户
        'Intended Audience :: Developers',

        # 主题
        'Topic :: Software Development :: Libraries',

        # 支持的 Python 版本
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',

        # 编程语言
        'Programming Language :: C++',
    ],
)

# ============================================================
# 使用说明
# ============================================================
# 1. 开发模式（推荐）：
#    python3 setup.py build_ext --inplace
#    这会在 python/miniray/ 目录下生成 _miniray_core.so
#
# 2. 安装到系统：
#    pip install .
#    这会将包安装到 Python 的 site-packages 目录
#
# 3. 开发安装（可编辑模式）：
#    pip install -e .
#    修改代码后不需要重新安装（但修改 C++ 代码需要重新编译）
#
# 4. 指定并行编译线程数：
#    python3 setup.py build_ext --inplace --parallel 8
#
# 5. 清理构建文件：
#    rm -rf build/ python/miniray/_miniray_core*.so
# ============================================================

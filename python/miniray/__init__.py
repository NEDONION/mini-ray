"""
Mini-Ray 包入口文件 (__init__.py)

这个文件的作用：
1. 定义包的公共 API（用户可以直接使用的函数和类）
2. 导入 C++ 核心模块（_miniray_core.so）
3. 导入 Python 封装层（api.py, actor.py 等）
4. 统一导出接口，让用户可以 `import miniray` 后直接使用

当用户执行 `import miniray` 时，Python 会自动执行这个文件。

用法示例:
    import miniray

    # 初始化（启动 Worker 进程）
    miniray.init(num_workers=4)

    # 定义远程函数
    @miniray.remote
    def add(a, b):
        return a + b

    # 提交任务，返回 ObjectRef（类似 Future）
    ref = add.remote(1, 2)

    # 获取结果（阻塞等待）
    result = miniray.get(ref)
    print(result)  # 3

    # 定义 Actor（有状态的远程对象）
    @miniray.remote
    class Counter:
        def __init__(self):
            self.value = 0

        def increment(self):
            self.value += 1
            return self.value

    # 创建 Actor 实例
    counter = Counter.remote()

    # 调用 Actor 方法
    result = miniray.get(counter.increment.remote())
    print(result)  # 1

    # 关闭 Mini-Ray
    miniray.shutdown()
"""

__version__ = "0.1.0"

# ============================================================
# 导入 C++ 核心模块
# ============================================================
# 这里尝试导入编译好的 C++ 扩展模块 _miniray_core.so
# 这个模块包含高性能的 C++ 实现：
# - ObjectStore（对象存储，基于共享内存）
# - ObjectRef（对象引用）
# - Scheduler（任务调度器）
# - CoreWorker（核心工作组件）
#
# 注意：from . import _miniray_core 表示从当前包导入
# 如果导入失败（例如 .so 文件未编译），会回退到纯 Python 实现
try:
    from . import _miniray_core

    # 导出 C++ 类供用户使用
    ObjectRef = _miniray_core.ObjectRef      # 对象引用
    ObjectStore = _miniray_core.ObjectStore  # 对象存储
    _use_cpp_core = True

except ImportError as e:
    # 如果 C++ 模块导入失败，使用纯 Python 实现作为后备
    print(f"Warning: Failed to import C++ core module: {e}")
    print("Falling back to pure Python implementation")
    from .core import ObjectRef
    _use_cpp_core = False

# ============================================================
# 导入 Python API 层
# ============================================================
# 这些是 Python 封装的高层 API，提供用户友好的接口
from .api import init, shutdown, get, remote

# ============================================================
# 定义公共 API（__all__）
# ============================================================
# __all__ 定义了 `from miniray import *` 时会导入哪些名称
# 这是 Python 包的最佳实践，明确声明公共接口
__all__ = [
    # 核心 API 函数
    'init',        # 初始化 Mini-Ray
    'shutdown',    # 关闭 Mini-Ray
    'get',         # 获取 ObjectRef 的值
    'remote',      # 装饰器，将函数/类转为远程可调用

    # 核心类型
    'ObjectRef',   # 对象引用（C++ 或 Python 实现）
    'ObjectStore', # 对象存储（仅 C++ 实现）
]

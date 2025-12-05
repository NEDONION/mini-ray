"""
pytest 配置文件 (conftest.py)

这个文件的作用：
1. 提供共享的 pytest fixtures（测试夹具）
2. 配置 pytest 的行为
3. 设置测试环境（例如路径设置）

Fixtures 是 pytest 的核心功能，用于提供测试所需的资源和环境。
"""
import sys
import os
import pytest

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 添加 python/miniray 目录到路径（_miniray_core.so 在这里）
MINI_RAY_DIR = os.path.join(PROJECT_ROOT, 'python', 'miniray')
if MINI_RAY_DIR not in sys.path:
    sys.path.insert(0, MINI_RAY_DIR)


@pytest.fixture(scope="session")
def core_module():
    """
    Session 级别的 fixture：导入 C++ 核心模块

    scope="session" 表示这个 fixture 在整个测试会话中只创建一次，
    所有测试都共享同一个模块对象。

    Returns:
        module: _miniray_core C++ 模块
    """
    try:
        import _miniray_core as core
        return core
    except ImportError as e:
        pytest.skip(f"无法导入 C++ 核心模块: {e}")


@pytest.fixture
def object_store(core_module):
    """
    Function 级别的 fixture：为每个测试创建新的 ObjectStore

    默认 scope="function"，每个测试函数都会获得一个全新的 ObjectStore，
    确保测试之间互不影响。

    Args:
        core_module: 依赖 core_module fixture

    Returns:
        ObjectStore: 新创建的 ObjectStore 实例
    """
    return core_module.ObjectStore()


@pytest.fixture
def sample_data():
    """
    提供测试用的样本数据

    Returns:
        dict: 包含各种类型数据的字典
    """
    return {
        'bytes': b"Hello, Mini-Ray!",
        'string': "Test String",
        'number': 42,
        'list': [1, 2, 3, 4, 5],
        'dict': {"key": "value", "number": 123}
    }


@pytest.fixture
def serialized_data(sample_data):
    """
    提供序列化后的测试数据

    Args:
        sample_data: 依赖 sample_data fixture

    Returns:
        dict: 键为数据类型，值为序列化后的 bytes
    """
    import pickle
    return {
        key: pickle.dumps(value)
        for key, value in sample_data.items()
    }

"""
pytest 配置文件

包含测试的全局 fixture 和配置
"""

import pytest
import sys
import os

# 确保可以导入 miniray
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="session")
def miniray_session():
    """
    会话级 fixture，初始化一次 Mini-Ray 系统供所有测试使用

    这样可以避免每个测试都重新初始化和关闭整个系统，大幅提高测试速度。
    """
    import miniray

    # 首先清理任何现有的共享内存
    try:
        import miniray._miniray_core as core
        core.cleanup_shared_memory()
    except:
        pass  # Ignore cleanup errors if no shared memory exists yet

    # 初始化 Mini-Ray 系统（使用较少的 worker 以节省资源）
    miniray.init(num_workers=2)

    yield miniray  # 返回 miniray 模块供测试使用

    # 测试结束后关闭系统
    miniray.shutdown()

    # Final cleanup
    try:
        import miniray._miniray_core as core
        core.cleanup_shared_memory()
    except:
        pass


@pytest.fixture(scope="function")
def miniray_instance(miniray_session):
    """
    函数级 fixture，确保每个测试都使用已初始化的 Mini-Ray 系统

    注意：由于整个测试会话共用一个 Mini-Ray 实例，因此每个测试
    应该确保不会影响其他测试的状态。
    """
    # 简单返回已初始化的会话实例
    yield miniray_session


@pytest.fixture(scope="session", autouse=True)
def cleanup_shared_memory():
    """
    清理共享内存的 fixture

    在所有测试结束后自动清理共享内存
    """
    yield

    # 测试结束后清理
    try:
        import miniray._miniray_core as core
        core.cleanup_shared_memory()
        print("\n[Cleanup] Shared memory cleaned up")
    except Exception as e:
        print(f"\n[Cleanup] Failed to cleanup shared memory: {e}")


@pytest.fixture
def temp_object_store():
    """
    创建临时对象存储的 fixture
    """
    import miniray._miniray_core as core

    store = core.ObjectStore(create=True)
    yield store

    # 清理
    try:
        core.cleanup_shared_memory()
    except:
        pass


@pytest.fixture
def temp_scheduler():
    """
    创建临时调度器的 fixture
    """
    import miniray._miniray_core as core

    scheduler = core.Scheduler(create=True)
    yield scheduler

    # 清理
    try:
        core.cleanup_shared_memory()
    except:
        pass

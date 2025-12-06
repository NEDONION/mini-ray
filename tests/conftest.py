"""
pytest 配置文件

包含测试的全局 fixture 和配置
"""

import pytest
import sys
import os

# 确保可以导入 miniray
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


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

"""
miniray Events 功能测试
测试事件系统功能
"""

import pytest


class TestEventsBasic:
    """Events基础功能测试"""
    
    def test_events_import(self):
        """测试Events模块导入"""
        import miniray
        
        # 测试events模块可以正常导入
        assert miniray.events is not None
        
        # 检查events模块基本功能
        assert hasattr(miniray.events, '__name__')
    
    def test_event_system_basic(self):
        """测试事件系统基础功能"""
        import miniray.events

        # 确保模块正确加载
        assert miniray.events is not None

        # 检查是否包含事件相关的基本组件
        assert hasattr(miniray.events, 'EventBus')
        assert hasattr(miniray.events, 'TaskEvent')
        assert hasattr(miniray.events, 'TaskEventType')
        assert hasattr(miniray.events, 'SharedStorage')

        # 测试创建事件总线实例
        event_bus = miniray.events.EventBus()
        assert event_bus is not None

        # 测试创建共享存储
        storage = miniray.events.SharedStorage()
        assert storage is not None
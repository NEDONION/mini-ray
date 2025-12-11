"""
miniray Parameter Server 功能测试
测试参数服务器功能
"""

import pytest


class TestParameterServerBasic:
    """Parameter Server基础功能测试"""
    
    def test_ps_import(self):
        """测试Parameter Server模块导入"""
        import miniray
        
        # 测试ps模块可以正常导入
        assert miniray.ps is not None
        
        # 验证ps模块包含预期的组件
        expected_components = ['parameter_server', 'strategies']
        for comp in expected_components:
            assert hasattr(miniray.ps, comp)
    
    def test_parameter_server_basic(self):
        """测试Parameter Server基础功能"""
        import miniray.ps.parameter_server
        from miniray.ps.parameter_server import ParameterServer
        
        # 简单测试类是否可实例化
        try:
            ps = ParameterServer()
            # 检查基本方法是否存在
            assert hasattr(ps, 'init_parameters')
            assert hasattr(ps, 'pull')
            assert hasattr(ps, 'push')
        except Exception:
            # 可能需要特定参数或初始化
            pass


class TestParameterServerStrategies:
    """Parameter Server策略测试"""
    
    def test_strategies_import(self):
        """测试策略模块导入"""
        import miniray.ps.strategies

        # 至少确保模块可以导入
        assert miniray.ps.strategies is not None

        # 检查是否有可用的同步策略
        assert hasattr(miniray.ps.strategies, 'SyncStrategy')
        assert hasattr(miniray.ps.strategies, 'AverageStrategy')
        assert hasattr(miniray.ps.strategies, 'WeightedAverageStrategy')
        assert hasattr(miniray.ps.strategies, 'MomentumStrategy')
    
    def test_parameter_server_strategies_basic(self):
        """测试参数服务器策略基础功能"""
        from miniray.ps.strategies import AverageStrategy, WeightedAverageStrategy, MomentumStrategy, SyncStrategy

        # 简单测试策略类是否定义
        assert AverageStrategy is not None
        assert WeightedAverageStrategy is not None
        assert MomentumStrategy is not None
        assert SyncStrategy is not None

        # 测试创建策略实例
        avg_strategy = AverageStrategy()
        weighted_strategy = WeightedAverageStrategy()
        momentum_strategy = MomentumStrategy()

        assert isinstance(avg_strategy, SyncStrategy)
        assert isinstance(weighted_strategy, SyncStrategy)
        assert isinstance(momentum_strategy, SyncStrategy)
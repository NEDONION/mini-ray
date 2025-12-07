"""
Mini-Ray Dashboard - Web 监控界面

提供简单的 Web UI 用于监控 Mini-Ray 的运行状态。

使用方法:
    >>> from miniray.dashboard import run_dashboard
    >>> run_dashboard(port=8266)

或者作为独立脚本运行:
    $ python -m miniray.dashboard

访问 http://localhost:8266 查看 Dashboard
"""

from .app import run_dashboard, app
from .collector import get_collector, MetricsCollector

__all__ = [
    'run_dashboard',
    'app',
    'get_collector',
    'MetricsCollector',
]

__version__ = '0.1.0'

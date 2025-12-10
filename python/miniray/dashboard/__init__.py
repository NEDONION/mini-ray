"""
Mini-Ray Dashboard - Web 监控界面

提供简单的 Web UI 用于监控 Mini-Ray 的运行状态。

使用方法:
    >>> from miniray.dashboard import run_dashboard
    >>> run_dashboard(port=8266)

或者作为独立脚本运行:
    $ python -m miniray.dashboard

访问 http://localhost:8266 查看 Dashboard

训练任务跟踪:
    >>> from miniray.dashboard.tracking import track_training_job
    >>> @track_training_job(name="My Training Job", description="A sample training task")
    >>> def my_training_function():
    >>>     return "Training completed"
"""

from .app import run_dashboard, app
from .collector import get_collector, MetricsCollector
from .tracking import track_training, track_training_job, track_inference_job, track_tuning_job

__all__ = [
    'run_dashboard',
    'app',
    'get_collector',
    'MetricsCollector',
    'track_training',
    'track_training_job',
    'track_inference_job',
    'track_tuning_job',
]

__version__ = '0.1.0'

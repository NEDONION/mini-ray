"""
Trial 数据结构 - 表示单次超参数试验
"""
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class Trial:
    """
    单次超参数试验

    Attributes:
        trial_id: 试验唯一标识
        config: 超参数配置
        status: 试验状态 (PENDING, RUNNING, COMPLETED, FAILED)
        result: 试验结果
        metrics: 记录的指标
        start_time: 开始时间
        end_time: 结束时间
        error: 错误信息（如果失败）
    """
    trial_id: str
    config: Dict[str, Any]
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    result: Optional[Any] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[Exception] = None

    def start(self):
        """标记试验开始"""
        self.status = "RUNNING"
        self.start_time = time.time()

    def complete(self, result: Any, metrics: Optional[Dict[str, Any]] = None):
        """标记试验完成"""
        self.status = "COMPLETED"
        self.result = result
        self.end_time = time.time()

        if metrics:
            self.metrics.update(metrics)

    def fail(self, error: Exception):
        """标记试验失败"""
        self.status = "FAILED"
        self.error = error
        self.end_time = time.time()

    @property
    def duration(self) -> Optional[float]:
        """计算试验耗时"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def __repr__(self):
        return (f"Trial(id={self.trial_id[:8]}, "
                f"status={self.status}, "
                f"config={self.config})")

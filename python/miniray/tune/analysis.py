"""
结果分析 - 分析超参数调优结果
"""
from typing import List, Dict, Any, Optional
from .trial import Trial


class Analysis:
    """
    超参数调优结果分析

    提供：
    - 获取最佳配置
    - 获取最佳 Trial
    - 获取所有 Trials
    - 生成结果报告
    """

    def __init__(
        self,
        trials: List[Trial],
        metric: str,
        mode: str = "max"
    ):
        """
        Args:
            trials: 所有试验
            metric: 优化指标名称
            mode: 优化模式 ('max' 或 'min')
        """
        self.trials = trials
        self.metric = metric
        self.mode = mode

        # 只保留成功的 trials
        self.successful_trials = [t for t in trials if t.status == "COMPLETED"]

    @property
    def best_trial(self) -> Optional[Trial]:
        """获取最佳 Trial"""
        if not self.successful_trials:
            return None

        # 根据 mode 选择最佳
        if self.mode == "max":
            return max(
                self.successful_trials,
                key=lambda t: self._get_metric_value(t)
            )
        else:  # mode == "min"
            return min(
                self.successful_trials,
                key=lambda t: self._get_metric_value(t)
            )

    @property
    def best_config(self) -> Optional[Dict[str, Any]]:
        """获取最佳配置"""
        if self.best_trial:
            return self.best_trial.config
        return None

    @property
    def best_result(self) -> Optional[Any]:
        """获取最佳结果"""
        if self.best_trial:
            return self.best_trial.result
        return None

    def get_best_trial(self, metric: Optional[str] = None, mode: Optional[str] = None) -> Optional[Trial]:
        """
        获取指定指标的最佳 Trial

        Args:
            metric: 指标名称（如果为 None，使用初始化时的 metric）
            mode: 优化模式（如果为 None，使用初始化时的 mode）

        Returns:
            最佳 Trial
        """
        metric = metric or self.metric
        mode = mode or self.mode

        if not self.successful_trials:
            return None

        if mode == "max":
            return max(
                self.successful_trials,
                key=lambda t: self._get_metric_value(t, metric)
            )
        else:
            return min(
                self.successful_trials,
                key=lambda t: self._get_metric_value(t, metric)
            )

    def get_all_trials(self) -> List[Trial]:
        """获取所有 Trials"""
        return self.trials

    def get_dataframe(self) -> Dict[str, List]:
        """
        将结果转换为字典格式（类似 DataFrame）

        Returns:
            字典，键是列名，值是列表
        """
        data = {
            'trial_id': [],
            'status': [],
            'config': [],
            'duration': [],
        }

        # 添加 metric 列
        data[self.metric] = []

        # 添加其他 metrics
        all_metric_keys = set()
        for trial in self.trials:
            all_metric_keys.update(trial.metrics.keys())

        for key in all_metric_keys:
            if key != self.metric:
                data[key] = []

        # 填充数据
        for trial in self.trials:
            data['trial_id'].append(trial.trial_id)
            data['status'].append(trial.status)
            data['config'].append(trial.config)
            data['duration'].append(trial.duration)

            # 主要 metric
            data[self.metric].append(self._get_metric_value(trial))

            # 其他 metrics
            for key in all_metric_keys:
                if key != self.metric:
                    data[key].append(trial.metrics.get(key, None))

        return data

    def stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        total = len(self.trials)
        completed = len(self.successful_trials)
        failed = len([t for t in self.trials if t.status == "FAILED"])

        stats = {
            'total_trials': total,
            'completed_trials': completed,
            'failed_trials': failed,
            'metric': self.metric,
            'mode': self.mode,
        }

        if self.best_trial:
            stats['best_config'] = self.best_config
            stats[f'best_{self.metric}'] = self._get_metric_value(self.best_trial)
            stats['best_trial_id'] = self.best_trial.trial_id

        return stats

    def summary(self) -> str:
        """
        生成结果摘要

        Returns:
            摘要字符串
        """
        stats = self.stats()

        lines = [
            "=" * 60,
            "  超参数调优结果摘要",
            "=" * 60,
            f"  总试验数: {stats['total_trials']}",
            f"  成功: {stats['completed_trials']}, 失败: {stats['failed_trials']}",
            f"  优化指标: {stats['metric']} (模式: {stats['mode']})",
            "",
        ]

        if self.best_trial:
            lines.extend([
                "  🏆 最佳配置:",
                f"      Trial ID: {stats['best_trial_id'][:8]}...",
                f"      {stats['metric']}: {stats[f'best_{self.metric}']:.4f}",
                f"      配置: {stats['best_config']}",
                "",
            ])

        # Top 5 trials
        if len(self.successful_trials) > 1:
            lines.append("  📊 Top 5 Trials:")

            # 排序
            sorted_trials = sorted(
                self.successful_trials,
                key=lambda t: self._get_metric_value(t),
                reverse=(self.mode == "max")
            )

            for i, trial in enumerate(sorted_trials[:5], 1):
                metric_val = self._get_metric_value(trial)
                lines.append(f"      {i}. {self.metric}={metric_val:.4f}, config={trial.config}")

        lines.append("=" * 60)

        return "\n".join(lines)

    def _get_metric_value(self, trial: Trial, metric: Optional[str] = None) -> float:
        """
        获取 Trial 的指标值

        Args:
            trial: Trial 对象
            metric: 指标名称

        Returns:
            指标值
        """
        metric = metric or self.metric

        # 优先从 metrics 字典获取
        if metric in trial.metrics:
            return trial.metrics[metric]

        # 如果 result 是字典，从中获取
        if isinstance(trial.result, dict) and metric in trial.result:
            return trial.result[metric]

        # 否则抛出错误
        raise ValueError(
            f"Metric '{metric}' not found in trial {trial.trial_id}. "
            f"Available metrics: {list(trial.metrics.keys())}"
        )

    def __repr__(self):
        return f"Analysis(trials={len(self.trials)}, metric={self.metric}, mode={self.mode})"

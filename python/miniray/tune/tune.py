"""
Tune 核心逻辑 - 超参数调优控制器
"""
import uuid
import time
from typing import Callable, Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .trial import Trial
from .search import SearchAlgorithm, GridSearchAlgorithm, RandomSearchAlgorithm, SearchSpace
from .analysis import Analysis


class TuneController:
    """
    超参数调优控制器

    负责：
    1. 生成超参数配置
    2. 调度试验执行
    3. 收集结果
    4. 生成分析报告
    """

    def __init__(
        self,
        trainable: Callable[[Dict[str, Any]], Dict[str, Any]],
        config: Dict[str, Any],
        metric: str = "score",
        mode: str = "max",
        num_samples: int = 1,
        search_alg: Optional[SearchAlgorithm] = None,
        max_concurrent: int = 4,
        verbose: bool = True
    ):
        """
        Args:
            trainable: 训练函数，接收 config，返回包含 metric 的字典
            config: 搜索空间配置
            metric: 优化指标名称
            mode: 优化模式 ('max' 或 'min')
            num_samples: 每个配置运行的次数
            search_alg: 搜索算法（如果为 None，自动选择）
            max_concurrent: 最大并发试验数
            verbose: 是否打印详细信息
        """
        self.trainable = trainable
        self.config = config
        self.metric = metric
        self.mode = mode
        self.num_samples = num_samples
        self.max_concurrent = max_concurrent
        self.verbose = verbose

        # 自动选择搜索算法
        if search_alg is None:
            # 检查是否有 RandomSearch
            has_random = any(
                isinstance(v, SearchSpace) and hasattr(v, 'num_samples')
                for v in config.values()
            )

            if has_random:
                self.search_alg = RandomSearchAlgorithm(num_samples=10)
            else:
                self.search_alg = GridSearchAlgorithm()
        else:
            self.search_alg = search_alg

        # 存储所有 trials
        self.trials: List[Trial] = []

    def run(self) -> Analysis:
        """
        运行超参数调优

        Returns:
            Analysis 对象，包含所有结果
        """
        if self.verbose:
            print("=" * 70)
            print("  开始超参数调优")
            print("=" * 70)
            print(f"  优化指标: {self.metric} (模式: {self.mode})")
            print(f"  搜索算法: {self.search_alg.__class__.__name__}")
            print(f"  最大并发: {self.max_concurrent}")
            print("")

        start_time = time.time()

        # 生成所有配置
        configs = list(self.search_alg.generate_configs(self.config))

        if self.verbose:
            print(f"  生成了 {len(configs)} 个配置")
            print(f"  每个配置运行 {self.num_samples} 次")
            print(f"  总试验数: {len(configs) * self.num_samples}")
            print("")

        # 为每个配置创建 trials（可能有多个 samples）
        all_trials = []
        for config in configs:
            for sample_idx in range(self.num_samples):
                trial_id = str(uuid.uuid4())
                trial = Trial(trial_id=trial_id, config=config)
                all_trials.append(trial)

        # 使用 Mini-Ray 并行执行 trials
        self._run_trials_with_miniray(all_trials)

        # 如果 Mini-Ray 失败，回退到本地并发执行
        # （这里作为备选方案）

        total_time = time.time() - start_time

        if self.verbose:
            print("")
            print("=" * 70)
            print(f"  调优完成！总耗时: {total_time:.2f}s")
            print("=" * 70)

        # 创建分析对象
        analysis = Analysis(
            trials=all_trials,
            metric=self.metric,
            mode=self.mode
        )

        if self.verbose:
            print(analysis.summary())

        return analysis

    def _run_trials_with_miniray(self, trials: List[Trial]):
        """
        使用 Mini-Ray 并行执行 trials

        Args:
            trials: 要执行的 trials 列表
        """
        try:
            import miniray
            from miniray.api import _initialized

            if not _initialized:
                if self.verbose:
                    print("  ⚠️  Mini-Ray 未初始化，使用本地并发执行")
                self._run_trials_local(trials)
                return

            if self.verbose:
                print(f"  🚀 使用 Mini-Ray 并行执行 {len(trials)} 个试验")
                print("")

            # 定义远程训练函数
            @miniray.remote
            def run_trial_remote(trial_dict: Dict[str, Any], trainable_func: Callable) -> Dict[str, Any]:
                """在 Worker 上运行单个 trial"""
                trial_id = trial_dict['trial_id']
                config = trial_dict['config']

                trial_result = {
                    'trial_id': trial_id,
                    'status': 'COMPLETED',
                    'start_time': time.time(),
                }

                try:
                    # 执行训练函数
                    result = trainable_func(config)

                    trial_result['result'] = result
                    trial_result['end_time'] = time.time()

                except Exception as e:
                    trial_result['status'] = 'FAILED'
                    trial_result['error'] = str(e)
                    trial_result['end_time'] = time.time()

                return trial_result

            # 提交所有 trials
            trial_refs = []
            for trial in trials:
                trial_dict = {
                    'trial_id': trial.trial_id,
                    'config': trial.config,
                }
                ref = run_trial_remote.remote(trial_dict, self.trainable)
                trial_refs.append((trial, ref))

            # 收集结果
            completed = 0
            for trial, ref in trial_refs:
                trial_result = miniray.get(ref)

                trial.trial_id = trial_result['trial_id']
                trial.status = trial_result['status']
                trial.start_time = trial_result['start_time']
                trial.end_time = trial_result['end_time']

                if trial.status == 'COMPLETED':
                    result = trial_result['result']
                    trial.complete(result, metrics=result if isinstance(result, dict) else {})
                    completed += 1

                    if self.verbose:
                        metric_val = trial.metrics.get(self.metric, 'N/A')
                        print(f"  [{completed}/{len(trials)}] Trial {trial.trial_id[:8]}: "
                              f"{self.metric}={metric_val}, "
                              f"耗时={trial.duration:.2f}s, "
                              f"config={trial.config}")
                else:
                    error_msg = trial_result.get('error', 'Unknown error')
                    trial.fail(Exception(error_msg))

                    if self.verbose:
                        print(f"  [{completed}/{len(trials)}] Trial {trial.trial_id[:8]}: FAILED - {error_msg}")

            self.trials = trials

        except ImportError:
            if self.verbose:
                print("  ⚠️  无法导入 miniray，使用本地并发执行")
            self._run_trials_local(trials)

        except Exception as e:
            if self.verbose:
                print(f"  ⚠️  Mini-Ray 执行失败: {e}")
                print("  回退到本地并发执行")
            self._run_trials_local(trials)

    def _run_trials_local(self, trials: List[Trial]):
        """
        使用本地线程池并发执行 trials（备选方案）

        Args:
            trials: 要执行的 trials 列表
        """
        if self.verbose:
            print(f"  🔧 使用本地并发执行 {len(trials)} 个试验")
            print("")

        def run_single_trial(trial: Trial) -> Trial:
            """运行单个 trial"""
            trial.start()

            try:
                result = self.trainable(trial.config)

                # 如果结果是字典，提取 metrics
                if isinstance(result, dict):
                    trial.complete(result, metrics=result)
                else:
                    # 否则创建包含单个 metric 的字典
                    trial.complete(result, metrics={self.metric: result})

            except Exception as e:
                trial.fail(e)

            return trial

        # 使用线程池并发执行
        completed = 0
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {executor.submit(run_single_trial, trial): trial for trial in trials}

            for future in as_completed(futures):
                trial = future.result()
                completed += 1

                if trial.status == 'COMPLETED':
                    if self.verbose:
                        metric_val = trial.metrics.get(self.metric, 'N/A')
                        print(f"  [{completed}/{len(trials)}] Trial {trial.trial_id[:8]}: "
                              f"{self.metric}={metric_val}, "
                              f"耗时={trial.duration:.2f}s, "
                              f"config={trial.config}")
                else:
                    if self.verbose:
                        print(f"  [{completed}/{len(trials)}] Trial {trial.trial_id[:8]}: "
                              f"FAILED - {trial.error}")

        self.trials = trials


def run(
    trainable: Callable[[Dict[str, Any]], Dict[str, Any]],
    config: Dict[str, Any],
    metric: str = "score",
    mode: str = "max",
    num_samples: int = 1,
    search_alg: Optional[str] = None,
    max_concurrent: int = 4,
    verbose: bool = True
) -> Analysis:
    """
    运行超参数调优（便捷函数）

    Args:
        trainable: 训练函数，接收 config 字典，返回包含 metric 的字典
        config: 搜索空间配置
        metric: 优化指标名称
        mode: 优化模式 ('max' 或 'min')
        num_samples: 每个配置运行的次数
        search_alg: 搜索算法名称 ('grid' 或 'random')
        max_concurrent: 最大并发试验数
        verbose: 是否打印详细信息

    Returns:
        Analysis 对象

    Example:
        >>> from miniray import tune
        >>> def train_fn(config):
        ...     model = Model(lr=config['lr'])
        ...     acc = model.train()
        ...     return {'accuracy': acc}
        ...
        >>> analysis = tune.run(
        ...     train_fn,
        ...     config={'lr': tune.grid_search([0.01, 0.1])},
        ...     metric='accuracy',
        ...     mode='max'
        ... )
    """
    # 选择搜索算法
    alg = None
    if search_alg == 'random':
        alg = RandomSearchAlgorithm(num_samples=10)
    elif search_alg == 'grid':
        alg = GridSearchAlgorithm()
    # 如果为 None，TuneController 会自动选择

    controller = TuneController(
        trainable=trainable,
        config=config,
        metric=metric,
        mode=mode,
        num_samples=num_samples,
        search_alg=alg,
        max_concurrent=max_concurrent,
        verbose=verbose
    )

    return controller.run()

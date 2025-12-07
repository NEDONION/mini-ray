"""
指标收集器 - 收集 Mini-Ray 的运行时指标

提供：
- 任务统计
- Worker 状态
- 系统指标（CPU、内存）
"""
import time
import psutil
from typing import Dict, List, Any, Optional
from collections import defaultdict
from threading import Lock


class MetricsCollector:
    """
    指标收集器（单例模式）

    收集和存储 Mini-Ray 的运行时指标
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # 任务统计
        self.tasks = []  # 所有任务记录
        self.task_counter = defaultdict(int)  # 按状态计数

        # Worker 状态
        self.workers = {}  # worker_id -> worker_info

        # 系统指标历史
        self.metrics_history = []
        self.max_history = 100  # 最多保留 100 条历史

        # 训练任务
        self.training_jobs = []  # 训练任务列表
        self.training_logs = {}  # task_id -> logs

        # 超参数调优实验
        self.tuning_experiments = []  # 调优实验列表
        self.tuning_trials = {}  # experiment_id -> trials

        # 推理服务
        self.inference_services = []  # 推理服务列表

        # 启动时间
        self.start_time = time.time()

    def record_task(
        self,
        task_id: str,
        status: str,
        config: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
        duration: Optional[float] = None
    ):
        """
        记录任务

        Args:
            task_id: 任务 ID
            status: 任务状态（PENDING, RUNNING, COMPLETED, FAILED）
            config: 任务配置
            result: 任务结果
            duration: 任务耗时
        """
        task_info = {
            'task_id': task_id,
            'status': status,
            'config': config or {},
            'result': result,
            'duration': duration,
            'timestamp': time.time(),
        }

        # 更新或添加任务
        existing_task = next((t for t in self.tasks if t['task_id'] == task_id), None)
        if existing_task:
            existing_task.update(task_info)
        else:
            self.tasks.append(task_info)

        # 更新计数器
        self.task_counter[status] += 1

    def update_worker(self, worker_id: int, status: str, info: Optional[Dict] = None):
        """
        更新 Worker 状态

        Args:
            worker_id: Worker ID
            status: Worker 状态（IDLE, BUSY, OFFLINE）
            info: 额外信息
        """
        self.workers[worker_id] = {
            'worker_id': worker_id,
            'status': status,
            'info': info or {},
            'last_updated': time.time(),
        }

    def get_system_info(self):
        """获取系统硬件信息（一次性，不变的信息）"""
        import platform

        info = {
            'system': platform.system(),  # Darwin, Linux, Windows
            'platform': platform.platform(),
            'machine': platform.machine(),  # x86_64, arm64
            'processor': platform.processor(),
            'cpu_count': psutil.cpu_count(logical=False),  # 物理核心
            'cpu_count_logical': psutil.cpu_count(logical=True),  # 逻辑核心
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'disk_total_gb': psutil.disk_usage('/').total / (1024**3),
        }

        # 尝试获取 GPU 信息（如果安装了相关库）
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            info['gpus'] = [{'name': gpu.name, 'memory_total_mb': gpu.memoryTotal} for gpu in gpus]
        except:
            info['gpus'] = []

        return info

    def collect_system_metrics(self):
        """收集系统实时指标"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        metrics = {
            'timestamp': time.time(),
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_gb': memory.used / (1024**3),
            'memory_total_gb': memory.total / (1024**3),
            'disk_percent': disk.percent,
            'disk_used_gb': disk.used / (1024**3),
            'disk_total_gb': disk.total / (1024**3),
        }

        self.metrics_history.append(metrics)

        # 保持历史记录在限制内
        if len(self.metrics_history) > self.max_history:
            self.metrics_history = self.metrics_history[-self.max_history:]

        return metrics

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        # 计算任务统计
        total_tasks = len(self.tasks)
        completed_tasks = sum(1 for t in self.tasks if t['status'] == 'COMPLETED')
        failed_tasks = sum(1 for t in self.tasks if t['status'] == 'FAILED')
        running_tasks = sum(1 for t in self.tasks if t['status'] == 'RUNNING')
        pending_tasks = sum(1 for t in self.tasks if t['status'] == 'PENDING')

        # 计算平均耗时
        completed_durations = [t['duration'] for t in self.tasks
                               if t['status'] == 'COMPLETED' and t['duration']]
        avg_duration = sum(completed_durations) / len(completed_durations) if completed_durations else 0

        # Worker 统计
        total_workers = len(self.workers)
        active_workers = sum(1 for w in self.workers.values() if w['status'] != 'OFFLINE')

        # 系统指标
        latest_metrics = self.metrics_history[-1] if self.metrics_history else {
            'cpu_percent': 0,
            'memory_percent': 0,
        }

        # 运行时间
        uptime = time.time() - self.start_time

        return {
            'tasks': {
                'total': total_tasks,
                'completed': completed_tasks,
                'failed': failed_tasks,
                'running': running_tasks,
                'pending': pending_tasks,
                'avg_duration': avg_duration,
            },
            'workers': {
                'total': total_workers,
                'active': active_workers,
            },
            'system': {
                'cpu_percent': latest_metrics['cpu_percent'],
                'memory_percent': latest_metrics['memory_percent'],
            },
            'uptime': uptime,
        }

    def get_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取任务列表

        Args:
            limit: 最多返回多少个任务

        Returns:
            任务列表（最新的在前面）
        """
        return sorted(self.tasks, key=lambda t: t['timestamp'], reverse=True)[:limit]

    def get_workers(self) -> List[Dict[str, Any]]:
        """
        获取 Worker 列表

        Returns:
            Worker 列表
        """
        return list(self.workers.values())

    def get_metrics_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取指标历史

        Args:
            limit: 最多返回多少条历史

        Returns:
            指标历史列表
        """
        return self.metrics_history[-limit:]

    def record_training_job(
        self,
        job_id: str,
        name: str,
        status: str,
        progress: float = 0.0,
        config: Optional[Dict] = None,
        metrics: Optional[Dict] = None
    ):
        """
        记录训练任务

        Args:
            job_id: 任务 ID
            name: 任务名称
            status: 状态（Pending, Running, Completed, Failed）
            progress: 进度 (0-100)
            config: 配置信息
            metrics: 训练指标
        """
        job_info = {
            'id': job_id,
            'name': name,
            'status': status,
            'progress': progress,
            'config': config or {},
            'metrics': metrics or {},
            'start_time': time.time(),
            'updated_at': time.time(),
        }

        # 更新或添加任务
        existing = next((j for j in self.training_jobs if j['id'] == job_id), None)
        if existing:
            existing.update(job_info)
            existing['updated_at'] = time.time()
        else:
            self.training_jobs.append(job_info)

    def add_training_log(self, job_id: str, log_line: str):
        """添加训练日志"""
        if job_id not in self.training_logs:
            self.training_logs[job_id] = []

        log_entry = {
            'timestamp': time.time(),
            'message': log_line
        }
        self.training_logs[job_id].append(log_entry)

    def get_training_jobs(self, limit: int = 50) -> List[Dict]:
        """获取训练任务列表"""
        return sorted(self.training_jobs, key=lambda j: j['updated_at'], reverse=True)[:limit]

    def get_training_logs(self, job_id: str, limit: int = 100) -> List[Dict]:
        """获取训练日志"""
        logs = self.training_logs.get(job_id, [])
        return logs[-limit:]

    def record_tuning_experiment(
        self,
        experiment_id: str,
        name: str,
        status: str,
        config: Optional[Dict] = None,
        best_config: Optional[Dict] = None,
        best_score: Optional[float] = None
    ):
        """
        记录超参数调优实验

        Args:
            experiment_id: 实验 ID
            name: 实验名称
            status: 状态
            config: 配置
            best_config: 最佳配置
            best_score: 最佳得分
        """
        exp_info = {
            'id': experiment_id,
            'name': name,
            'status': status,
            'config': config or {},
            'best_config': best_config,
            'best_score': best_score,
            'created_at': time.time(),
            'updated_at': time.time(),
        }

        existing = next((e for e in self.tuning_experiments if e['id'] == experiment_id), None)
        if existing:
            existing.update(exp_info)
            existing['updated_at'] = time.time()
        else:
            self.tuning_experiments.append(exp_info)

    def record_tuning_trial(
        self,
        experiment_id: str,
        trial_id: str,
        config: Dict,
        status: str,
        score: Optional[float] = None,
        metrics: Optional[Dict] = None
    ):
        """记录 Trial"""
        if experiment_id not in self.tuning_trials:
            self.tuning_trials[experiment_id] = []

        trial_info = {
            'id': trial_id,
            'experiment_id': experiment_id,
            'config': config,
            'status': status,
            'score': score,
            'metrics': metrics or {},
            'created_at': time.time(),
        }

        self.tuning_trials[experiment_id].append(trial_info)

    def get_tuning_experiments(self, limit: int = 50) -> List[Dict]:
        """获取调优实验列表"""
        return sorted(self.tuning_experiments, key=lambda e: e['updated_at'], reverse=True)[:limit]

    def get_tuning_trials(self, experiment_id: str) -> List[Dict]:
        """获取实验的 Trial 列表"""
        return self.tuning_trials.get(experiment_id, [])

    def record_inference_service(
        self,
        service_id: str,
        name: str,
        status: str,
        model_name: str = "",
        endpoint: str = "",
        config: Optional[Dict] = None,
        stats: Optional[Dict] = None
    ):
        """
        记录推理服务

        Args:
            service_id: 服务 ID
            name: 服务名称
            status: 状态
            model_name: 模型名称
            endpoint: 端点地址
            config: 配置
            stats: 统计信息
        """
        service_info = {
            'id': service_id,
            'name': name,
            'status': status,
            'model': model_name,
            'endpoint': endpoint,
            'config': config or {},
            'stats': stats or {'requests': 0, 'avg_latency': 0},
            'created_at': time.time(),
            'updated_at': time.time(),
        }

        existing = next((s for s in self.inference_services if s['id'] == service_id), None)
        if existing:
            existing.update(service_info)
            existing['updated_at'] = time.time()
        else:
            self.inference_services.append(service_info)

    def get_inference_services(self) -> List[Dict]:
        """获取推理服务列表"""
        return sorted(self.inference_services, key=lambda s: s['updated_at'], reverse=True)

    def reset(self):
        """重置所有指标"""
        self.tasks = []
        self.task_counter = defaultdict(int)
        self.workers = {}
        self.metrics_history = []
        self.training_jobs = []
        self.training_logs = {}
        self.tuning_experiments = []
        self.tuning_trials = {}
        self.inference_services = []
        self.start_time = time.time()


# 全局单例
_collector = MetricsCollector()


def get_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    return _collector

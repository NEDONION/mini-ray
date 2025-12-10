"""
Mini-Ray Dashboard - Flask 应用

提供简单的 Web UI 监控 Mini-Ray 的运行状态
"""
import os
import signal
from flask import Flask, render_template, jsonify, request
from .collector import get_collector


# 创建 Flask 应用
app = Flask(__name__)

# 获取指标收集器
collector = get_collector()


# ============================================================
# 页面路由
# ============================================================

@app.route('/')
def index():
    """主页 - 新版 Dashboard（完全真实数据，无 mock）"""
    return render_template('dashboard.html')

# ============================================================
# API 路由
# ============================================================

@app.route('/api/system-info')
def get_system_info():
    """
    获取系统硬件信息

    Returns:
        JSON 格式的系统信息（CPU型号、内存、磁盘、GPU等）
    """
    system_info = collector.get_system_info()
    return jsonify(system_info)


@app.route('/api/stats')
def get_stats():
    """
    获取统计信息

    Returns:
        JSON 格式的统计信息
    """
    stats = collector.get_stats()
    return jsonify(stats)


@app.route('/api/tasks')
def get_tasks():
    """
    获取任务列表

    Returns:
        JSON 格式的任务列表
    """
    limit = 50  # 最多返回 50 个任务

    # 从持久化存储获取任务
    try:
        storage = collector._storage
        all_tasks = storage.get_all_tasks()
        # 按更新时间排序，最新的在前
        sorted_tasks = sorted(all_tasks, key=lambda x: x.get('updated_at', 0), reverse=True)
        tasks = sorted_tasks[:limit]
    except:
        # 备用方案：直接从events模块获取
        from ..events import get_shared_storage
        storage = get_shared_storage()
        all_tasks = storage.get_all_tasks()
        # 按更新时间排序，最新的在前
        sorted_tasks = sorted(all_tasks, key=lambda x: x.get('updated_at', 0), reverse=True)
        tasks = sorted_tasks[:limit]

    return jsonify({
        'tasks': tasks,
        'total': len(tasks)
    })


@app.route('/api/workers')
def get_workers():
    """
    获取 Worker 列表

    Returns:
        JSON 格式的 Worker 列表
    """
    workers = collector.get_workers()

    return jsonify({
        'workers': workers,
        'total': len(workers)
    })


@app.route('/api/metrics')
def get_metrics():
    """
    获取系统指标

    Returns:
        JSON 格式的系统指标
    """
    # 收集最新的系统指标
    latest_metrics = collector.collect_system_metrics()

    # 获取历史指标
    history = collector.get_metrics_history(limit=50)

    return jsonify({
        'latest': latest_metrics,
        'history': history
    })


@app.route('/api/training-jobs')
def get_training_jobs():
    """
    获取训练任务列表

    Returns:
        JSON 格式的训练任务列表
    """
    # 从持久化存储获取训练任务
    try:
        storage = collector._storage
        all_tasks = storage.get_all_tasks()
        # 过滤出训练任务
        training_jobs = [task for task in all_tasks if task.get('type') == 'training']
        # 按更新时间排序，最新的在前
        sorted_jobs = sorted(training_jobs, key=lambda x: x.get('updated_at', 0), reverse=True)
        jobs = sorted_jobs[:50]
    except:
        # 备用方案：直接从events模块获取
        from ..events import get_shared_storage
        storage = get_shared_storage()
        all_tasks = storage.get_all_tasks()
        # 过滤出训练任务
        training_jobs = [task for task in all_tasks if task.get('type') == 'training']
        # 按更新时间排序，最新的在前
        sorted_jobs = sorted(training_jobs, key=lambda x: x.get('updated_at', 0), reverse=True)
        jobs = sorted_jobs[:50]

    return jsonify({
        'jobs': jobs,
        'total': len(jobs)
    })


@app.route('/api/training-jobs/<job_id>/logs')
def get_training_job_logs(job_id):
    """
    获取训练任务日志

    Args:
        job_id: 任务 ID

    Returns:
        JSON 格式的日志列表
    """
    logs = collector.get_training_logs(job_id, limit=200)
    return jsonify({
        'job_id': job_id,
        'logs': logs,
        'total': len(logs)
    })


@app.route('/api/tuning-experiments')
def get_tuning_experiments():
    """
    获取超参数调优实验列表

    Returns:
        JSON 格式的实验列表
    """
    experiments = collector.get_tuning_experiments(limit=50)
    return jsonify({
        'experiments': experiments,
        'total': len(experiments)
    })


@app.route('/api/tuning-experiments/<experiment_id>/trials')
def get_tuning_trials(experiment_id):
    """
    获取实验的 Trial 列表

    Args:
        experiment_id: 实验 ID

    Returns:
        JSON 格式的 Trial 列表
    """
    trials = collector.get_tuning_trials(experiment_id)
    return jsonify({
        'experiment_id': experiment_id,
        'trials': trials,
        'total': len(trials)
    })


@app.route('/api/inference-services')
def get_inference_services():
    """
    获取推理服务列表

    Returns:
        JSON 格式的推理服务列表
    """
    services = collector.get_inference_services()
    return jsonify({
        'services': services,
        'total': len(services)
    })


# ============================================================
# 启动函数
# ============================================================

def run_dashboard(host='0.0.0.0', port=8266, debug=False):
    """
    启动 Dashboard

    Args:
        host: 监听地址
        port: 监听端口（默认 8266，避免与 Ray 的 8265 冲突）
        debug: 是否开启调试模式
    """
    print("=" * 70)
    print("  Mini-Ray Dashboard 启动中...")
    print("=" * 70)
    print(f"  访问地址: http://localhost:{port}")
    print("=" * 70)

    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    run_dashboard(debug=True)

#!/usr/bin/env python3
"""
ML 训练和推理 Demo - Dashboard 集成版

展示：
1. 数据并行训练 - 多个 worker 训练模型
2. 分布式批量推理 - 多个服务器处理推理请求
3. 所有任务实时显示在 Dashboard 上

使用方法:
    1. 先启动 Dashboard: python examples/test_dashboard_v2.py
    2. 在另一个终端运行此脚本: python examples/04_ml_training_with_dashboard.py
    3. 在浏览器查看 http://localhost:8266 实时监控
"""
import sys
import os
import time
import numpy as np

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'python'))

import miniray
from miniray.dashboard import get_collector


# ============================================================
# Demo 1: 数据并行训练
# ============================================================

@miniray.remote
class TrainingWorker:
    """训练 Worker - 在本地训练模型的一部分"""

    def __init__(self, worker_id, model_name="RandomForest"):
        self.worker_id = worker_id
        self.model_name = model_name
        print(f"[Worker {worker_id}] 初始化完成")

    def train(self, X_train, y_train, job_id):
        """训练模型"""
        collector = get_collector()

        # 记录训练开始
        collector.add_training_log(job_id, f"[INFO] Worker {self.worker_id} 开始训练")

        print(f"[Worker {self.worker_id}] 开始训练，数据量: {len(X_train)} 样本")

        # 模拟训练过程
        epochs = 10
        for epoch in range(epochs):
            time.sleep(0.5)  # 模拟训练时间

            # 模拟训练指标
            loss = 2.0 * np.exp(-epoch / 3) + np.random.rand() * 0.1
            accuracy = 1.0 - loss / 2.0

            # 更新进度
            progress = (epoch + 1) / epochs * 100
            collector.record_training_job(
                job_id=job_id,
                name=f"{self.model_name} Training",
                status='Running',
                progress=progress,
                config={'model': self.model_name, 'worker': self.worker_id, 'epochs': epochs},
                metrics={'loss': float(loss), 'accuracy': float(accuracy), 'epoch': epoch + 1}
            )

            # 添加日志
            log_msg = f"[INFO] Worker {self.worker_id} | Epoch {epoch+1}/{epochs} | Loss: {loss:.4f} | Acc: {accuracy:.4f}"
            collector.add_training_log(job_id, log_msg)
            print(f"[Worker {self.worker_id}] Epoch {epoch+1}/{epochs} - Loss: {loss:.4f}, Acc: {accuracy:.4f}")

        final_accuracy = accuracy

        # 训练完成
        collector.record_training_job(
            job_id=job_id,
            name=f"{self.model_name} Training",
            status='Completed',
            progress=100.0,
            config={'model': self.model_name, 'worker': self.worker_id, 'epochs': epochs},
            metrics={'loss': float(loss), 'accuracy': float(final_accuracy)}
        )
        collector.add_training_log(job_id, f"[SUCCESS] Worker {self.worker_id} 训练完成！最终准确率: {final_accuracy:.4f}")

        print(f"[Worker {self.worker_id}] 训练完成！最终准确率: {final_accuracy:.4f}")

        return {
            'worker_id': self.worker_id,
            'accuracy': float(final_accuracy),
            'loss': float(loss)
        }


def demo1_data_parallel_training():
    """Demo 1: 数据并行训练"""
    print("\n" + "="*70)
    print("  Demo 1: 数据并行训练")
    print("="*70 + "\n")

    collector = get_collector()
    job_id = f"job-dp-{int(time.time())}"

    # 创建训练任务记录
    collector.record_training_job(
        job_id=job_id,
        name="Data Parallel Training",
        status='Pending',
        progress=0.0,
        config={'model': 'RandomForest', 'workers': 3, 'strategy': 'data_parallel'},
        metrics={}
    )
    collector.add_training_log(job_id, "[INFO] 数据并行训练任务已创建")

    # 生成模拟数据
    print("📊 生成训练数据...")
    n_samples = 3000
    n_features = 20
    X = np.random.randn(n_samples, n_features)
    y = (X.sum(axis=1) > 0).astype(int)

    # 将数据分成 3 份
    n_workers = 3
    chunk_size = n_samples // n_workers

    print(f"📦 将数据分成 {n_workers} 份，每份 {chunk_size} 样本")
    print(f"🚀 启动 {n_workers} 个训练 Worker...")
    collector.add_training_log(job_id, f"[INFO] 启动 {n_workers} 个 Worker 进行并行训练")

    # 创建 Worker
    workers = [TrainingWorker.remote(i, "RandomForest") for i in range(n_workers)]

    # 分发数据并行训练
    train_refs = []
    for i, worker in enumerate(workers):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size
        X_chunk = X[start_idx:end_idx]
        y_chunk = y[start_idx:end_idx]

        ref = worker.train.remote(X_chunk, y_chunk, job_id)
        train_refs.append(ref)

    # 获取训练结果
    print("\n⏳ 等待所有 Worker 完成训练...\n")
    results = miniray.get(train_refs)

    # 聚合结果
    avg_accuracy = np.mean([r['accuracy'] for r in results])
    print(f"\n✅ 所有 Worker 训练完成！")
    print(f"📈 平均准确率: {avg_accuracy:.4f}")

    worker_acc_list = [f"{r['accuracy']:.4f}" for r in results]
    print(f"📊 各 Worker 准确率: {worker_acc_list}")

    collector.add_training_log(job_id, f"[SUCCESS] 训练完成！平均准确率: {avg_accuracy:.4f}")

    return results


# ============================================================
# Demo 2: 分布式批量推理
# ============================================================

@miniray.remote
class InferenceServer:
    """推理服务器"""

    def __init__(self, server_id, model_name="Classifier"):
        self.server_id = server_id
        self.model_name = model_name
        self.request_count = 0
        print(f"[Server {server_id}] 推理服务器启动")

    def predict(self, X_batch, service_id):
        """批量推理"""
        collector = get_collector()

        batch_size = len(X_batch)
        self.request_count += batch_size

        # 模拟推理时间
        start_time = time.time()
        time.sleep(0.1)  # 模拟推理延迟

        # 生成模拟预测结果
        predictions = (X_batch.sum(axis=1) > 0).astype(int)

        latency = (time.time() - start_time) * 1000  # ms

        # 更新服务统计
        collector.record_inference_service(
            service_id=service_id,
            name=f"Inference Server {self.server_id}",
            status='Online',
            model_name=self.model_name,
            endpoint=f"http://server-{self.server_id}:8000",
            config={'server_id': self.server_id, 'model': self.model_name},
            stats={'requests': self.request_count, 'avg_latency': latency}
        )

        print(f"[Server {self.server_id}] 处理 {batch_size} 个请求，延迟: {latency:.1f}ms")

        return predictions


def demo2_distributed_inference():
    """Demo 2: 分布式批量推理"""
    print("\n" + "="*70)
    print("  Demo 2: 分布式批量推理")
    print("="*70 + "\n")

    collector = get_collector()

    # 生成推理数据
    print("📊 生成推理数据...")
    n_samples = 1000
    n_features = 20
    X = np.random.randn(n_samples, n_features)

    # 创建推理服务器
    n_servers = 3
    print(f"🚀 启动 {n_servers} 个推理服务器...")

    servers = []
    for i in range(n_servers):
        server = InferenceServer.remote(i, "Classifier")
        servers.append(server)

        # 注册服务
        service_id = f"svc-{i}"
        collector.record_inference_service(
            service_id=service_id,
            name=f"Inference Server {i}",
            status='Online',
            model_name="Classifier",
            endpoint=f"http://server-{i}:8000",
            config={'server_id': i, 'replicas': 1},
            stats={'requests': 0, 'avg_latency': 0}
        )

    # 分发推理任务
    batch_size = n_samples // n_servers
    print(f"📦 将数据分成 {n_servers} 批，每批 {batch_size} 样本")
    print(f"\n⏳ 开始分布式推理...\n")

    predict_refs = []
    for i, server in enumerate(servers):
        start_idx = i * batch_size
        end_idx = start_idx + batch_size
        X_batch = X[start_idx:end_idx]

        ref = server.predict.remote(X_batch, f"svc-{i}")
        predict_refs.append(ref)

    # 获取推理结果
    predictions_list = miniray.get(predict_refs)
    all_predictions = np.concatenate(predictions_list)

    print(f"\n✅ 推理完成！")
    print(f"📊 处理样本数: {len(all_predictions)}")
    print(f"📈 预测分布: {np.bincount(all_predictions)}")

    return all_predictions


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "="*70)
    print("  Mini-Ray ML Training & Inference Demo")
    print("  with Dashboard Integration")
    print("="*70)

    print("\n💡 提示:")
    print("  1. 确保 Dashboard 已启动: http://localhost:8266")
    print("  2. 在 Dashboard 的 Training Jobs 页面可以看到训练进度")
    print("  3. 在 Inference 页面可以看到推理服务")
    print()

    # 初始化 Mini-Ray
    print("🔧 初始化 Mini-Ray...")
    miniray.init(num_workers=4)
    time.sleep(1)

    collector = get_collector()

    # 注册 Workers
    for i in range(4):
        collector.update_worker(i, 'IDLE')

    # 收集系统指标
    collector.collect_system_metrics()

    try:
        # Demo 1: 数据并行训练
        demo1_data_parallel_training()

        time.sleep(2)

        # Demo 2: 分布式推理
        demo2_distributed_inference()

        print("\n" + "="*70)
        print("  ✅ 所有 Demo 完成！")
        print("="*70)
        print("\n💡 在 Dashboard 查看所有训练任务和推理服务:")
        print("   http://localhost:8266")
        print()

    finally:
        print("\n🔧 关闭 Mini-Ray...")
        miniray.shutdown()
        print("✅ Demo 结束\n")


if __name__ == "__main__":
    main()

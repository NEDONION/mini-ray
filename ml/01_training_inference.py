#!/usr/bin/env python3
"""
Mini-Ray ML 训练和推理 Demo

展示如何使用 Mini-Ray 进行分布式机器学习：
1. 数据并行训练（Data Parallel Training）
2. 分布式批量推理（Distributed Batch Inference）
3. 参数服务器模式（Parameter Server）

使用 scikit-learn 的随机森林作为示例模型
"""
import sys
import os
import time
import numpy as np

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import miniray


def print_section(title):
    """打印分隔线和标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def generate_synthetic_data(n_samples=10000, n_features=20, n_classes=3, random_state=42):
    """
    生成合成分类数据集

    Args:
        n_samples: 样本数量
        n_features: 特征数量
        n_classes: 类别数量
        random_state: 随机种子

    Returns:
        X: 特征矩阵 (n_samples, n_features)
        y: 标签向量 (n_samples,)
    """
    np.random.seed(random_state)

    # 生成特征
    X = np.random.randn(n_samples, n_features)

    # 生成标签（多类分类）
    # 每个类有一些特征倾向
    y = np.zeros(n_samples, dtype=int)
    for i in range(n_classes):
        # 第 i 类在某些特征上有正向偏移
        class_indices = np.arange(i * (n_samples // n_classes),
                                   (i + 1) * (n_samples // n_classes))
        y[class_indices] = i
        X[class_indices, i * 5:(i + 1) * 5] += 2.0  # 增加类间区分度

    # 打乱数据
    shuffle_idx = np.random.permutation(n_samples)
    X = X[shuffle_idx]
    y = y[shuffle_idx]

    return X, y


# ============================================================
# Demo 1: 数据并行训练（Data Parallel Training）
# ============================================================

def demo_1_data_parallel_training():
    """
    演示 1: 数据并行训练

    策略：
    - 将数据分片，每个 Worker 训练自己的模型副本
    - 每个 Worker 在自己的数据分片上训练
    - 主进程聚合所有模型的预测结果（集成学习）
    """
    print_section("Demo 1: 数据并行训练（Data Parallel Training）")

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, classification_report
    except ImportError:
        print("⚠️  需要安装 scikit-learn: pip install scikit-learn")
        return

    # 定义训练 Worker Actor
    @miniray.remote
    class TrainingWorker:
        def __init__(self, worker_id, n_estimators=50):
            self.worker_id = worker_id
            self.model = RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=10,
                random_state=worker_id,
                n_jobs=1
            )
            print(f"  [Worker-{worker_id}] 初始化完成")

        def train(self, X_train, y_train):
            """训练模型"""
            print(f"  [Worker-{self.worker_id}] 开始训练，数据量: {len(X_train)}")
            start_time = time.time()

            self.model.fit(X_train, y_train)

            train_time = time.time() - start_time
            train_acc = self.model.score(X_train, y_train)

            print(f"  [Worker-{self.worker_id}] 训练完成，耗时: {train_time:.2f}s，训练准确率: {train_acc:.4f}")

            return {
                'worker_id': self.worker_id,
                'train_time': train_time,
                'train_accuracy': train_acc,
                'n_samples': len(X_train)
            }

        def predict(self, X_test):
            """预测"""
            print(f"  [Worker-{self.worker_id}] 开始推理，样本数: {len(X_test)}")
            predictions = self.model.predict(X_test)
            return predictions

        def get_feature_importance(self):
            """获取特征重要性"""
            return self.model.feature_importances_

    print("\n📌 第 1 步: 生成合成数据集")
    X, y = generate_synthetic_data(n_samples=10000, n_features=20, n_classes=3)
    print(f"  数据集大小: {X.shape}, 类别数: {len(np.unique(y))}")

    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"  训练集: {X_train.shape}, 测试集: {X_test.shape}")

    print("\n📌 第 2 步: 创建 4 个训练 Worker")
    num_workers = 4
    workers = []
    for i in range(num_workers):
        worker = TrainingWorker.remote(worker_id=i, n_estimators=50)
        workers.append(worker)
        print(f"  → 创建 Worker-{i}")
    time.sleep(0.5)

    print("\n📌 第 3 步: 数据分片 - 将训练数据分配给各个 Worker")
    # 将训练数据分成 num_workers 份
    X_shards = np.array_split(X_train, num_workers)
    y_shards = np.array_split(y_train, num_workers)

    for i in range(num_workers):
        print(f"  Shard-{i}: {X_shards[i].shape[0]} 样本")

    print("\n📌 第 4 步: 并行训练所有 Worker")
    train_refs = []
    for i, worker in enumerate(workers):
        ref = worker.train.remote(X_shards[i], y_shards[i])
        train_refs.append(ref)
        print(f"  → 提交 Worker-{i} 的训练任务")

    print("\n  ⏳ 等待所有 Worker 完成训练...")
    train_results = miniray.get(train_refs)

    print("\n  ✅ 训练结果汇总:")
    total_time = max(r['train_time'] for r in train_results)
    avg_acc = np.mean([r['train_accuracy'] for r in train_results])
    print(f"      总训练时间: {total_time:.2f}s (并行)")
    print(f"      平均训练准确率: {avg_acc:.4f}")

    for result in train_results:
        print(f"      Worker-{result['worker_id']}: "
              f"耗时 {result['train_time']:.2f}s, "
              f"准确率 {result['train_accuracy']:.4f}")

    print("\n📌 第 5 步: 使用所有模型进行集成预测（投票）")
    predict_refs = []
    for worker in workers:
        ref = worker.predict.remote(X_test)
        predict_refs.append(ref)

    print("  ⏳ 等待所有 Worker 完成预测...")
    all_predictions = miniray.get(predict_refs)

    # 投票集成：每个样本取多数投票
    all_predictions = np.array(all_predictions)  # shape: (num_workers, n_test_samples)
    ensemble_predictions = np.apply_along_axis(
        lambda x: np.bincount(x).argmax(),
        axis=0,
        arr=all_predictions
    )

    ensemble_acc = accuracy_score(y_test, ensemble_predictions)

    print(f"\n  ✅ 集成模型测试准确率: {ensemble_acc:.4f}")
    print("\n  📊 分类报告:")
    print(classification_report(y_test, ensemble_predictions,
                                target_names=[f'Class-{i}' for i in range(3)]))

    print("\n📌 第 6 步: 获取特征重要性")
    importance_refs = [worker.get_feature_importance.remote() for worker in workers]
    all_importance = miniray.get(importance_refs)

    # 平均特征重要性
    avg_importance = np.mean(all_importance, axis=0)
    top_5_features = np.argsort(avg_importance)[-5:][::-1]

    print("\n  ✅ Top 5 重要特征:")
    for idx in top_5_features:
        print(f"      特征 {idx}: 重要性 = {avg_importance[idx]:.4f}")

    print("\n📌 第 7 步: 关闭所有 Worker")
    for i, worker in enumerate(workers):
        worker.shutdown()
        print(f"  ✓ Worker-{i} 已关闭")


# ============================================================
# Demo 2: 分布式批量推理（Distributed Batch Inference）
# ============================================================

def demo_2_distributed_inference():
    """
    演示 2: 分布式批量推理

    场景：已有训练好的模型，需要对大量数据进行推理
    策略：将推理数据分片，并行推理，提高吞吐量
    """
    print_section("Demo 2: 分布式批量推理（Distributed Batch Inference）")

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
    except ImportError:
        print("⚠️  需要安装 scikit-learn: pip install scikit-learn")
        return

    # 定义推理服务 Actor
    @miniray.remote
    class InferenceServer:
        def __init__(self, server_id, model_params):
            self.server_id = server_id
            self.model = RandomForestClassifier(**model_params)
            self.request_count = 0
            print(f"  [InferenceServer-{server_id}] 初始化完成")

        def load_model(self, X_train, y_train):
            """加载（训练）模型"""
            print(f"  [InferenceServer-{self.server_id}] 训练模型...")
            self.model.fit(X_train, y_train)
            train_acc = self.model.score(X_train, y_train)
            print(f"  [InferenceServer-{self.server_id}] 模型训练完成，准确率: {train_acc:.4f}")
            return train_acc

        def predict_batch(self, X_batch):
            """批量推理"""
            self.request_count += 1
            start_time = time.time()

            predictions = self.model.predict(X_batch)
            probabilities = self.model.predict_proba(X_batch)

            inference_time = time.time() - start_time
            throughput = len(X_batch) / inference_time

            print(f"  [InferenceServer-{self.server_id}] "
                  f"推理完成: {len(X_batch)} 样本, "
                  f"耗时 {inference_time:.3f}s, "
                  f"吞吐量 {throughput:.0f} samples/s")

            return {
                'predictions': predictions,
                'probabilities': probabilities,
                'inference_time': inference_time,
                'throughput': throughput
            }

        def get_stats(self):
            """获取统计信息"""
            return {
                'server_id': self.server_id,
                'request_count': self.request_count
            }

    print("\n📌 第 1 步: 生成数据集")
    X_train, y_train = generate_synthetic_data(n_samples=5000, n_features=20, n_classes=3)
    X_inference, _ = generate_synthetic_data(n_samples=20000, n_features=20, n_classes=3,
                                             random_state=100)
    print(f"  训练集: {X_train.shape}")
    print(f"  推理数据: {X_inference.shape}")

    print("\n📌 第 2 步: 创建 3 个推理服务器")
    num_servers = 3
    model_params = {
        'n_estimators': 100,
        'max_depth': 10,
        'random_state': 42,
        'n_jobs': 1
    }

    servers = []
    for i in range(num_servers):
        server = InferenceServer.remote(server_id=i, model_params=model_params)
        servers.append(server)
        print(f"  → 创建 InferenceServer-{i}")
    time.sleep(0.3)

    print("\n📌 第 3 步: 所有服务器加载模型（训练）")
    load_refs = [server.load_model.remote(X_train, y_train) for server in servers]
    load_results = miniray.get(load_refs)
    print(f"  ✅ 所有服务器模型加载完成，平均训练准确率: {np.mean(load_results):.4f}")

    print("\n📌 第 4 步: 将推理数据分成批次")
    batch_size = 500
    num_batches = len(X_inference) // batch_size
    X_batches = [X_inference[i*batch_size:(i+1)*batch_size] for i in range(num_batches)]
    print(f"  总批次数: {num_batches}, 每批大小: {batch_size}")

    print("\n📌 第 5 步: 分布式批量推理（轮询调度）")
    print("  ⏳ 开始推理...")

    inference_start = time.time()
    inference_refs = []

    # 将批次轮询分配给各个服务器
    for i, batch in enumerate(X_batches):
        server = servers[i % num_servers]
        ref = server.predict_batch.remote(batch)
        inference_refs.append(ref)

    # 收集所有结果
    inference_results = miniray.get(inference_refs)
    total_inference_time = time.time() - inference_start

    print(f"\n  ✅ 推理完成！")
    print(f"      总耗时: {total_inference_time:.2f}s")
    print(f"      总样本数: {len(X_inference)}")
    print(f"      总吞吐量: {len(X_inference) / total_inference_time:.0f} samples/s")

    # 合并所有预测结果
    all_predictions = np.concatenate([r['predictions'] for r in inference_results])
    all_probabilities = np.concatenate([r['probabilities'] for r in inference_results])

    print(f"\n  📊 预测结果统计:")
    for cls in range(3):
        count = np.sum(all_predictions == cls)
        pct = count / len(all_predictions) * 100
        print(f"      Class-{cls}: {count} 样本 ({pct:.1f}%)")

    print("\n📌 第 6 步: 获取服务器统计信息")
    stats_refs = [server.get_stats.remote() for server in servers]
    stats = miniray.get(stats_refs)

    print("  📊 服务器负载:")
    for stat in stats:
        print(f"      Server-{stat['server_id']}: 处理了 {stat['request_count']} 个批次")

    print("\n📌 第 7 步: 关闭所有服务器")
    for i, server in enumerate(servers):
        server.shutdown()
        print(f"  ✓ InferenceServer-{i} 已关闭")


# ============================================================
# Demo 3: 参数服务器训练（Parameter Server Training）
# ============================================================

def demo_3_parameter_server():
    """
    演示 3: 参数服务器模式训练

    这是一个简化版的参数服务器，展示分布式梯度下降的基本流程
    """
    print_section("Demo 3: 参数服务器模式（Parameter Server）")

    # 定义参数服务器
    @miniray.remote
    class ParameterServer:
        def __init__(self, dim):
            self.params = np.zeros(dim)
            self.version = 0
            self.gradient_history = []
            print(f"  [ParameterServer] 初始化，参数维度: {dim}")

        def get_params(self):
            """获取当前参数"""
            return self.params.copy(), self.version

        def update_params(self, gradients, learning_rate=0.01):
            """更新参数"""
            self.params -= learning_rate * gradients
            self.version += 1
            self.gradient_history.append(np.linalg.norm(gradients))

            print(f"  [ParameterServer] 参数更新 (v{self.version}), "
                  f"梯度范数: {np.linalg.norm(gradients):.4f}, "
                  f"参数范数: {np.linalg.norm(self.params):.4f}")

            return self.version

        def get_stats(self):
            """获取统计信息"""
            return {
                'version': self.version,
                'param_norm': float(np.linalg.norm(self.params)),
                'param_mean': float(np.mean(self.params)),
                'param_std': float(np.std(self.params)),
                'gradient_history': self.gradient_history
            }

    # 定义训练 Worker
    @miniray.remote
    class GradientWorker:
        def __init__(self, worker_id, data_shard):
            self.worker_id = worker_id
            self.X, self.y = data_shard
            print(f"  [GradientWorker-{worker_id}] 初始化，数据量: {len(self.X)}")

        def compute_gradient(self, params):
            """
            计算梯度（这里使用简化的线性回归梯度）
            梯度 = (1/n) * X^T * (X*params - y)
            """
            n = len(self.X)
            predictions = self.X @ params
            errors = predictions - self.y
            gradient = (self.X.T @ errors) / n

            mse = np.mean(errors ** 2)

            print(f"  [GradientWorker-{self.worker_id}] "
                  f"计算梯度完成, MSE: {mse:.4f}, "
                  f"梯度范数: {np.linalg.norm(gradient):.4f}")

            return gradient, mse

    print("\n📌 第 1 步: 生成线性回归数据")
    n_samples = 10000
    n_features = 50

    # 生成真实参数
    true_params = np.random.randn(n_features) * 0.5

    # 生成数据
    X = np.random.randn(n_samples, n_features)
    y = X @ true_params + np.random.randn(n_samples) * 0.1  # 加入噪声

    print(f"  数据集: {X.shape}")
    print(f"  真实参数范数: {np.linalg.norm(true_params):.4f}")

    print("\n📌 第 2 步: 创建参数服务器")
    ps = ParameterServer.remote(dim=n_features)
    time.sleep(0.2)

    print("\n📌 第 3 步: 创建 4 个梯度计算 Worker")
    num_workers = 4

    # 数据分片
    X_shards = np.array_split(X, num_workers)
    y_shards = np.array_split(y, num_workers)

    workers = []
    for i in range(num_workers):
        worker = GradientWorker.remote(
            worker_id=i,
            data_shard=(X_shards[i], y_shards[i])
        )
        workers.append(worker)
        print(f"  → 创建 Worker-{i}, 数据量: {len(X_shards[i])}")
    time.sleep(0.3)

    print("\n📌 第 4 步: 参数服务器训练循环")
    num_epochs = 10
    learning_rate = 0.01

    print(f"  开始训练: {num_epochs} 轮, 学习率: {learning_rate}")

    for epoch in range(num_epochs):
        print(f"\n  --- Epoch {epoch + 1}/{num_epochs} ---")

        # 1. 获取当前参数
        params_ref = ps.get_params.remote()
        params, version = miniray.get(params_ref)
        print(f"    1️⃣ 获取参数 (v{version}), 范数: {np.linalg.norm(params):.4f}")

        # 2. 所有 Worker 并行计算梯度
        gradient_refs = []
        for i, worker in enumerate(workers):
            ref = worker.compute_gradient.remote(params)
            gradient_refs.append(ref)

        print(f"    2️⃣ Workers 并行计算梯度...")
        gradient_results = miniray.get(gradient_refs)

        gradients = [r[0] for r in gradient_results]
        mses = [r[1] for r in gradient_results]
        avg_mse = np.mean(mses)

        print(f"    3️⃣ 平均 MSE: {avg_mse:.4f}")

        # 3. 平均梯度
        avg_gradient = np.mean(gradients, axis=0)
        print(f"    4️⃣ 平均梯度范数: {np.linalg.norm(avg_gradient):.4f}")

        # 4. 更新参数服务器
        update_ref = ps.update_params.remote(avg_gradient, learning_rate)
        new_version = miniray.get(update_ref)

    print("\n📌 第 5 步: 获取最终统计")
    stats_ref = ps.get_stats.remote()
    stats = miniray.get(stats_ref)

    print("\n  ✅ 训练完成！最终统计:")
    print(f"      参数版本: {stats['version']}")
    print(f"      参数范数: {stats['param_norm']:.4f}")
    print(f"      参数均值: {stats['param_mean']:.4f}")
    print(f"      参数标准差: {stats['param_std']:.4f}")

    print("\n  📈 梯度范数历史:")
    for i, grad_norm in enumerate(stats['gradient_history'][:5]):
        print(f"      Epoch {i+1}: {grad_norm:.4f}")
    if len(stats['gradient_history']) > 5:
        print(f"      ...")
        for i, grad_norm in enumerate(stats['gradient_history'][-3:],
                                       start=len(stats['gradient_history'])-2):
            print(f"      Epoch {i}: {grad_norm:.4f}")

    print("\n📌 第 6 步: 关闭所有 Actor")
    ps.shutdown()
    print("  ✓ ParameterServer 已关闭")
    for i, worker in enumerate(workers):
        worker.shutdown()
        print(f"  ✓ Worker-{i} 已关闭")


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  Mini-Ray ML 训练和推理演示")
    print("=" * 70)
    print("\n本演示展示三种常见的分布式 ML 模式：")
    print("  1. 数据并行训练 - 将数据分片，每个 Worker 训练独立模型")
    print("  2. 分布式批量推理 - 将推理任务分配给多个服务器")
    print("  3. 参数服务器 - 集中式参数管理，分布式梯度计算")

    # 初始化 Mini-Ray
    print("\n" + "=" * 70)
    print("  初始化 Mini-Ray")
    print("=" * 70)
    miniray.init(num_workers=4)
    time.sleep(0.5)

    try:
        # 运行演示
        demo_1_data_parallel_training()
        demo_2_distributed_inference()
        demo_3_parameter_server()

        # 总结
        print_section("演示完成")
        print("\n✅ 所有 ML 演示都成功完成！")
        print("\n📊 演示内容回顾:")
        print("  1. 数据并行训练 - 训练 4 个模型副本并集成")
        print("  2. 分布式批量推理 - 3 个服务器处理 20000 样本")
        print("  3. 参数服务器 - 10 轮迭代训练线性模型")

        print("\n💡 关键要点:")
        print("  • Actor 模型非常适合有状态的 ML 组件（模型、参数服务器）")
        print("  • 并行化可以显著提高训练和推理的吞吐量")
        print("  • 参数服务器是经典的分布式训练架构")

        print("\n🚀 下一步:")
        print("  • 实现 miniray.tune 进行超参数调优")
        print("  • 添加更复杂的 ML 模型（神经网络）")
        print("  • 实现模型检查点和容错机制")

    finally:
        # 关闭 Mini-Ray
        print("\n" + "=" * 70)
        print("  关闭 Mini-Ray")
        print("=" * 70)
        miniray.shutdown()


if __name__ == "__main__":
    main()

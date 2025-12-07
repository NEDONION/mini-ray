#!/usr/bin/env python3
"""
Mini-Ray 超参数调优 Demo

展示如何使用 miniray.tune 进行超参数搜索：
1. 网格搜索（Grid Search）
2. 随机搜索（Random Search）
3. 实际 ML 模型调优（使用 sklearn）

这是 Phase 3 的核心功能之一！
"""
import sys
import os
import time

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import miniray
from miniray import tune


def print_section(title):
    """打印分隔线和标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ============================================================
# Demo 1: 简单的网格搜索
# ============================================================

def demo_1_simple_grid_search():
    """
    演示 1: 简单的网格搜索

    使用一个简单的函数来展示 tune 的基本用法
    """
    print_section("Demo 1: 简单的网格搜索")

    def simple_objective(config):
        """
        简单的目标函数

        Args:
            config: 超参数配置

        Returns:
            包含 score 的字典
        """
        x = config['x']
        y = config['y']

        # 目标：最大化 -(x-3)^2 - (y-5)^2 + 10
        # 最优解：x=3, y=5, score=10
        score = -(x - 3) ** 2 - (y - 5) ** 2 + 10

        # 模拟计算时间
        time.sleep(0.05)

        return {'score': score, 'x': x, 'y': y}

    print("\n📌 搜索空间:")
    print("  x: [0, 1, 2, 3, 4, 5, 6]")
    print("  y: [2, 3, 4, 5, 6, 7, 8]")
    print(f"  总配置数: 7 × 7 = 49")
    print("\n📌 目标函数: 最大化 -(x-3)² - (y-5)² + 10")
    print("  理论最优解: x=3, y=5, score=10")
    print("")

    # 运行调优
    analysis = tune.run(
        simple_objective,
        config={
            'x': tune.grid_search([0, 1, 2, 3, 4, 5, 6]),
            'y': tune.grid_search([2, 3, 4, 5, 6, 7, 8]),
        },
        metric='score',
        mode='max',
        verbose=True
    )

    print("\n📊 调优结果:")
    print(f"  最佳配置: {analysis.best_config}")
    print(f"  最佳得分: {analysis.best_result['score']:.4f}")
    print(f"  成功试验数: {len(analysis.successful_trials)}")


# ============================================================
# Demo 2: 随机森林超参数调优
# ============================================================

def demo_2_random_forest_tuning():
    """
    演示 2: 随机森林超参数调优

    使用真实的机器学习模型进行超参数搜索
    """
    print_section("Demo 2: 随机森林超参数调优")

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.datasets import load_digits
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score
    except ImportError:
        print("⚠️  需要安装 scikit-learn: pip install scikit-learn")
        return

    print("\n📌 第 1 步: 加载数据集（MNIST 手写数字）")
    X, y = load_digits(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"  训练集: {X_train.shape}, 测试集: {X_test.shape}")

    def train_random_forest(config):
        """
        训练随机森林模型

        Args:
            config: 超参数配置

        Returns:
            包含 accuracy 的字典
        """
        # 创建模型
        model = RandomForestClassifier(
            n_estimators=config['n_estimators'],
            max_depth=config['max_depth'],
            min_samples_split=config['min_samples_split'],
            random_state=42,
            n_jobs=1
        )

        # 训练
        start_time = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - start_time

        # 评估
        train_acc = accuracy_score(y_train, model.predict(X_train))
        test_acc = accuracy_score(y_test, model.predict(X_test))

        return {
            'accuracy': test_acc,
            'train_accuracy': train_acc,
            'train_time': train_time,
        }

    print("\n📌 第 2 步: 定义搜索空间")
    print("  n_estimators: [50, 100, 200]")
    print("  max_depth: [5, 10, 20, None]")
    print("  min_samples_split: [2, 5, 10]")
    print(f"  总配置数: 3 × 4 × 3 = 36")
    print("")

    # 运行调优
    analysis = tune.run(
        train_random_forest,
        config={
            'n_estimators': tune.grid_search([50, 100, 200]),
            'max_depth': tune.grid_search([5, 10, 20, None]),
            'min_samples_split': tune.grid_search([2, 5, 10]),
        },
        metric='accuracy',
        mode='max',
        verbose=True
    )

    print("\n📊 详细结果分析:")
    print(f"  最佳测试准确率: {analysis.best_result['accuracy']:.4f}")
    print(f"  最佳训练准确率: {analysis.best_result['train_accuracy']:.4f}")
    print(f"  训练耗时: {analysis.best_result['train_time']:.2f}s")
    print(f"  最佳配置:")
    for key, value in analysis.best_config.items():
        print(f"    {key}: {value}")


# ============================================================
# Demo 3: 神经网络超参数调优（简化版）
# ============================================================

def demo_3_neural_network_tuning():
    """
    演示 3: 神经网络超参数调优

    使用 sklearn 的 MLPClassifier 模拟神经网络调优
    """
    print_section("Demo 3: 神经网络超参数调优")

    try:
        from sklearn.neural_network import MLPClassifier
        from sklearn.datasets import make_classification
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("⚠️  需要安装 scikit-learn: pip install scikit-learn")
        return

    print("\n📌 第 1 步: 生成合成数据集")
    X, y = make_classification(
        n_samples=2000,
        n_features=20,
        n_informative=15,
        n_redundant=5,
        n_classes=3,
        random_state=42
    )

    # 标准化
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )
    print(f"  训练集: {X_train.shape}, 测试集: {X_test.shape}")

    def train_mlp(config):
        """
        训练神经网络

        Args:
            config: 超参数配置

        Returns:
            包含 accuracy 的字典
        """
        # 创建模型
        model = MLPClassifier(
            hidden_layer_sizes=config['hidden_layers'],
            learning_rate_init=config['learning_rate'],
            batch_size=config['batch_size'],
            max_iter=200,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1,
            verbose=False
        )

        # 训练
        start_time = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - start_time

        # 评估
        test_acc = accuracy_score(y_test, model.predict(X_test))
        train_acc = accuracy_score(y_train, model.predict(X_train))

        return {
            'accuracy': test_acc,
            'train_accuracy': train_acc,
            'train_time': train_time,
            'n_iter': model.n_iter_,
        }

    print("\n📌 第 2 步: 定义搜索空间")
    print("  hidden_layers: [(50,), (100,), (50, 50), (100, 50)]")
    print("  learning_rate: [0.001, 0.01, 0.1]")
    print("  batch_size: [32, 64, 128]")
    print(f"  总配置数: 4 × 3 × 3 = 36")
    print("")

    # 运行调优
    analysis = tune.run(
        train_mlp,
        config={
            'hidden_layers': tune.grid_search([
                (50,),      # 单隐藏层 50 个神经元
                (100,),     # 单隐藏层 100 个神经元
                (50, 50),   # 两层，每层 50 个
                (100, 50),  # 两层，100 和 50
            ]),
            'learning_rate': tune.grid_search([0.001, 0.01, 0.1]),
            'batch_size': tune.grid_search([32, 64, 128]),
        },
        metric='accuracy',
        mode='max',
        verbose=True
    )

    print("\n📊 详细结果分析:")
    print(f"  最佳测试准确率: {analysis.best_result['accuracy']:.4f}")
    print(f"  最佳训练准确率: {analysis.best_result['train_accuracy']:.4f}")
    print(f"  训练耗时: {analysis.best_result['train_time']:.2f}s")
    print(f"  迭代次数: {analysis.best_result['n_iter']}")
    print(f"  最佳配置:")
    for key, value in analysis.best_config.items():
        print(f"    {key}: {value}")


# ============================================================
# Demo 4: 对比不同搜索策略
# ============================================================

def demo_4_compare_strategies():
    """
    演示 4: 对比网格搜索和随机搜索

    在同一个问题上对比两种搜索策略的效果
    """
    print_section("Demo 4: 对比网格搜索和随机搜索")

    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.datasets import load_breast_cancer
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score
    except ImportError:
        print("⚠️  需要安装 scikit-learn: pip install scikit-learn")
        return

    print("\n📌 第 1 步: 加载数据集（乳腺癌分类）")
    X, y = load_breast_cancer(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"  训练集: {X_train.shape}, 测试集: {X_test.shape}")

    def train_gbdt(config):
        """训练梯度提升树"""
        model = GradientBoostingClassifier(
            n_estimators=config['n_estimators'],
            learning_rate=config['learning_rate'],
            max_depth=config['max_depth'],
            random_state=42
        )

        model.fit(X_train, y_train)
        test_acc = accuracy_score(y_test, model.predict(X_test))

        return {'accuracy': test_acc}

    # 策略 1: 网格搜索
    print("\n📌 策略 1: 网格搜索")
    print("  搜索空间: 3 × 3 × 3 = 27 个配置")

    grid_analysis = tune.run(
        train_gbdt,
        config={
            'n_estimators': tune.grid_search([50, 100, 200]),
            'learning_rate': tune.grid_search([0.01, 0.1, 0.5]),
            'max_depth': tune.grid_search([3, 5, 7]),
        },
        metric='accuracy',
        mode='max',
        verbose=False  # 不打印详细信息
    )

    print(f"\n  ✅ 网格搜索结果:")
    print(f"      试验数: {len(grid_analysis.trials)}")
    print(f"      最佳准确率: {grid_analysis.best_result['accuracy']:.4f}")
    print(f"      最佳配置: {grid_analysis.best_config}")

    # 策略 2: 随机搜索
    print("\n📌 策略 2: 随机搜索（10 次采样）")

    random_analysis = tune.run(
        train_gbdt,
        config={
            'n_estimators': tune.random_search([50, 100, 200], num_samples=10),
            'learning_rate': tune.random_search([0.01, 0.1, 0.5], num_samples=10),
            'max_depth': tune.random_search([3, 5, 7], num_samples=10),
        },
        metric='accuracy',
        mode='max',
        search_alg='random',
        verbose=False
    )

    print(f"\n  ✅ 随机搜索结果:")
    print(f"      试验数: {len(random_analysis.trials)}")
    print(f"      最佳准确率: {random_analysis.best_result['accuracy']:.4f}")
    print(f"      最佳配置: {random_analysis.best_config}")

    print("\n📊 对比总结:")
    print(f"  网格搜索: {len(grid_analysis.trials)} 次试验, "
          f"准确率 {grid_analysis.best_result['accuracy']:.4f}")
    print(f"  随机搜索: {len(random_analysis.trials)} 次试验, "
          f"准确率 {random_analysis.best_result['accuracy']:.4f}")
    print(f"  结论: 随机搜索用更少的试验找到了 "
          f"{'更好' if random_analysis.best_result['accuracy'] > grid_analysis.best_result['accuracy'] else '接近'}"
          f"的结果")


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  Mini-Ray 超参数调优演示")
    print("=" * 70)
    print("\n本演示展示 miniray.tune 的强大功能：")
    print("  • 网格搜索（Grid Search）- 穷举所有组合")
    print("  • 随机搜索（Random Search）- 高效采样")
    print("  • 自动并行执行 - 利用 Mini-Ray 加速")
    print("  • 结果分析 - 自动找到最佳配置")

    # 初始化 Mini-Ray
    print("\n" + "=" * 70)
    print("  初始化 Mini-Ray")
    print("=" * 70)
    miniray.init(num_workers=4)
    time.sleep(0.5)

    try:
        # 运行演示
        demo_1_simple_grid_search()
        demo_2_random_forest_tuning()
        demo_3_neural_network_tuning()
        demo_4_compare_strategies()

        # 总结
        print_section("演示完成")
        print("\n✅ 所有超参数调优演示都成功完成！")
        print("\n📊 演示内容回顾:")
        print("  1. 简单网格搜索 - 找到最优 (x, y) 组合")
        print("  2. 随机森林调优 - 36 个配置，找到最佳参数")
        print("  3. 神经网络调优 - 优化网络结构和学习率")
        print("  4. 策略对比 - 网格搜索 vs 随机搜索")

        print("\n💡 关键要点:")
        print("  • tune.run() 提供简洁的 API")
        print("  • tune.grid_search() 用于网格搜索")
        print("  • tune.random_search() 用于随机搜索")
        print("  • Analysis 对象提供结果分析")
        print("  • 自动利用 Mini-Ray 并行加速")

        print("\n🚀 下一步:")
        print("  • 查看 python/miniray/tune/ 了解实现细节")
        print("  • 在自己的 ML 项目中使用 tune")
        print("  • 实现更多搜索算法（贝叶斯优化等）")

    finally:
        # 关闭 Mini-Ray
        print("\n" + "=" * 70)
        print("  关闭 Mini-Ray")
        print("=" * 70)
        miniray.shutdown()


if __name__ == "__main__":
    main()

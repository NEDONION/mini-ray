#!/usr/bin/env python3
"""
Phase 3 Actor 演示脚本

展示 Mini-Ray Actor 模型的各种功能：
1. 简单计数器 Actor
2. 状态管理和累加器
3. 多个 Actor 并发
4. 参数服务器模式（ML 应用）
"""
import sys
import os
import time

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import miniray


def print_section(title):
    """打印分隔线和标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def demo_1_simple_counter():
    """演示 1: 简单的计数器 Actor"""
    print_section("演示 1: 简单计数器 Actor")

    # 定义 Counter Actor
    @miniray.remote
    class Counter:
        def __init__(self, initial_value=0):
            self.value = initial_value
            print(f"  [Counter] 初始化，初始值 = {initial_value}")

        def increment(self):
            self.value += 1
            print(f"  [Counter] 递增后，当前值 = {self.value}")
            return self.value

        def decrement(self):
            self.value -= 1
            print(f"  [Counter] 递减后，当前值 = {self.value}")
            return self.value

        def get_value(self):
            print(f"  [Counter] 获取值 = {self.value}")
            return self.value

    print("\n📌 创建 Counter Actor（初始值 = 10）")
    counter = Counter.remote(initial_value=10)
    time.sleep(0.2)  # 等待 Actor 初始化

    print("\n📌 调用 increment() 方法 3 次")
    refs = []
    for i in range(3):
        ref = counter.increment.remote()
        refs.append(ref)
        print(f"  → 提交第 {i+1} 次递增任务，ObjectRef: {ref}")

    print("\n📌 获取结果")
    results = miniray.get(refs)
    for i, result in enumerate(results):
        print(f"  ✓ 第 {i+1} 次递增结果: {result}")

    print("\n📌 调用 get_value() 获取当前值")
    current_ref = counter.get_value.remote()
    current_value = miniray.get(current_ref)
    print(f"  ✓ 当前计数器值: {current_value}")

    print("\n📌 关闭 Actor")
    counter.shutdown()
    print("  ✓ Counter Actor 已关闭")


def demo_2_accumulator():
    """演示 2: 累加器 - 状态管理"""
    print_section("演示 2: 累加器 - 状态管理")

    @miniray.remote
    class Accumulator:
        def __init__(self):
            self.total = 0
            self.count = 0
            self.values = []
            print(f"  [Accumulator] 初始化")

        def add(self, value):
            self.total += value
            self.count += 1
            self.values.append(value)
            print(f"  [Accumulator] 添加 {value}，总和 = {self.total}，数量 = {self.count}")
            return self.total

        def get_average(self):
            if self.count == 0:
                return 0
            avg = self.total / self.count
            print(f"  [Accumulator] 计算平均值 = {avg}")
            return avg

        def get_stats(self):
            stats = {
                'total': self.total,
                'count': self.count,
                'average': self.total / self.count if self.count > 0 else 0,
                'values': self.values
            }
            print(f"  [Accumulator] 获取统计信息: {stats}")
            return stats

    print("\n📌 创建 Accumulator Actor")
    acc = Accumulator.remote()
    time.sleep(0.2)

    print("\n📌 添加一系列数值: [10, 20, 30, 40, 50]")
    values = [10, 20, 30, 40, 50]
    refs = []
    for v in values:
        ref = acc.add.remote(v)
        refs.append(ref)
        print(f"  → 提交 add({v})")

    print("\n📌 获取累加结果")
    results = miniray.get(refs)
    for i, result in enumerate(results):
        print(f"  ✓ 添加第 {i+1} 个值后，总和 = {result}")

    print("\n📌 获取平均值")
    avg_ref = acc.get_average.remote()
    avg = miniray.get(avg_ref)
    print(f"  ✓ 平均值 = {avg}")

    print("\n📌 获取完整统计信息")
    stats_ref = acc.get_stats.remote()
    stats = miniray.get(stats_ref)
    print(f"  ✓ 统计信息:")
    for key, value in stats.items():
        print(f"      {key}: {value}")

    print("\n📌 关闭 Actor")
    acc.shutdown()
    print("  ✓ Accumulator Actor 已关闭")


def demo_3_multiple_actors():
    """演示 3: 多个 Actor 并发运行"""
    print_section("演示 3: 多个 Actor 并发运行")

    @miniray.remote
    class NamedCounter:
        def __init__(self, name, initial=0):
            self.name = name
            self.value = initial
            print(f"  [{self.name}] 初始化，初始值 = {initial}")

        def increment(self, step=1):
            self.value += step
            print(f"  [{self.name}] 递增 {step}，当前值 = {self.value}")
            return {'name': self.name, 'value': self.value}

        def get_info(self):
            info = {'name': self.name, 'value': self.value}
            print(f"  [{self.name}] 获取信息: {info}")
            return info

    print("\n📌 创建 3 个 NamedCounter Actor")
    counters = []
    names = ['Alpha', 'Beta', 'Gamma']
    initials = [0, 100, 200]

    for name, initial in zip(names, initials):
        counter = NamedCounter.remote(name, initial=initial)
        counters.append(counter)
        print(f"  → 创建 {name} (初始值={initial})")

    time.sleep(0.3)

    print("\n📌 并发递增所有 Counter")
    refs = []
    for i, counter in enumerate(counters):
        step = (i + 1) * 10  # Alpha +10, Beta +20, Gamma +30
        ref = counter.increment.remote(step=step)
        refs.append(ref)
        print(f"  → {names[i]}.increment(step={step})")

    print("\n📌 获取递增结果")
    results = miniray.get(refs)
    for result in results:
        print(f"  ✓ {result['name']}: 当前值 = {result['value']}")

    print("\n📌 获取所有 Counter 的完整信息")
    info_refs = [counter.get_info.remote() for counter in counters]
    infos = miniray.get(info_refs)
    for info in infos:
        print(f"  ✓ {info['name']}: value = {info['value']}")

    print("\n📌 关闭所有 Actor")
    for counter, name in zip(counters, names):
        counter.shutdown()
        print(f"  ✓ {name} Actor 已关闭")


def demo_4_parameter_server():
    """演示 4: 参数服务器模式（ML 应用）"""
    print_section("演示 4: 参数服务器模式（ML 应用）")

    try:
        import numpy as np
    except ImportError:
        print("⚠️  需要安装 numpy: pip install numpy")
        return

    @miniray.remote
    class ParameterServer:
        def __init__(self, dim):
            self.params = np.zeros(dim)
            self.version = 0
            print(f"  [ParamServer] 初始化，参数维度 = {dim}")

        def get_params(self):
            print(f"  [ParamServer] 获取参数 (version={self.version})")
            return self.params.copy(), self.version

        def update_params(self, gradients):
            learning_rate = 0.01
            self.params -= learning_rate * gradients
            self.version += 1
            print(f"  [ParamServer] 更新参数 (version={self.version})")
            print(f"      梯度范数: {np.linalg.norm(gradients):.4f}")
            print(f"      参数范数: {np.linalg.norm(self.params):.4f}")
            return self.version

        def get_stats(self):
            stats = {
                'version': self.version,
                'param_norm': float(np.linalg.norm(self.params)),
                'param_mean': float(np.mean(self.params)),
                'param_std': float(np.std(self.params))
            }
            print(f"  [ParamServer] 统计信息: {stats}")
            return stats

    @miniray.remote
    class Worker:
        def __init__(self, worker_id):
            self.worker_id = worker_id
            print(f"  [Worker-{worker_id}] 初始化")

        def compute_gradients(self, params):
            # 模拟梯度计算（随机梯度）
            gradients = np.random.randn(*params.shape) * 0.1
            print(f"  [Worker-{self.worker_id}] 计算梯度，范数 = {np.linalg.norm(gradients):.4f}")
            return gradients

    print("\n📌 创建参数服务器（维度 = 10）")
    ps = ParameterServer.remote(dim=10)
    time.sleep(0.2)

    print("\n📌 创建 2 个 Worker")
    workers = []
    for i in range(2):
        worker = Worker.remote(worker_id=i)
        workers.append(worker)
        print(f"  → 创建 Worker-{i}")
    time.sleep(0.2)

    print("\n📌 执行 3 轮训练迭代")
    for epoch in range(3):
        print(f"\n--- 轮次 {epoch + 1} ---")

        # 1. 获取当前参数
        print("  1️⃣ 获取当前参数")
        params_ref = ps.get_params.remote()
        params, version = miniray.get(params_ref)
        print(f"      参数版本: {version}")
        print(f"      参数范数: {np.linalg.norm(params):.4f}")

        # 2. Workers 并行计算梯度
        print("  2️⃣ Workers 并行计算梯度")
        gradient_refs = []
        for i, worker in enumerate(workers):
            ref = worker.compute_gradients.remote(params)
            gradient_refs.append(ref)
            print(f"      → Worker-{i} 开始计算梯度")

        gradients = miniray.get(gradient_refs)
        print(f"      ✓ 收到 {len(gradients)} 个梯度")

        # 3. 平均梯度
        avg_gradient = np.mean(gradients, axis=0)
        print(f"  3️⃣ 平均梯度")
        print(f"      平均梯度范数: {np.linalg.norm(avg_gradient):.4f}")

        # 4. 更新参数
        print(f"  4️⃣ 更新参数服务器")
        update_ref = ps.update_params.remote(avg_gradient)
        new_version = miniray.get(update_ref)
        print(f"      ✓ 参数更新完成，新版本: {new_version}")

    print("\n📌 获取最终统计信息")
    stats_ref = ps.get_stats.remote()
    stats = miniray.get(stats_ref)
    print("  ✓ 最终统计:")
    for key, value in stats.items():
        print(f"      {key}: {value}")

    print("\n📌 关闭所有 Actor")
    ps.shutdown()
    print("  ✓ ParameterServer 已关闭")
    for i, worker in enumerate(workers):
        worker.shutdown()
        print(f"  ✓ Worker-{i} 已关闭")


def demo_5_actor_features():
    """演示 5: Actor 特性汇总"""
    print_section("演示 5: Actor 特性汇总")

    @miniray.remote
    class FeatureDemo:
        def __init__(self, name):
            self.name = name
            self.call_count = 0
            print(f"  [FeatureDemo-{name}] 初始化")

        def slow_operation(self, duration):
            """模拟耗时操作"""
            self.call_count += 1
            print(f"  [FeatureDemo-{self.name}] 开始耗时操作 ({duration}s)...")
            time.sleep(duration)
            print(f"  [FeatureDemo-{self.name}] 耗时操作完成")
            return f"完成 ({self.call_count} 次调用)"

        def handle_error(self, should_error):
            """演示异常处理"""
            self.call_count += 1
            if should_error:
                print(f"  [FeatureDemo-{self.name}] 触发异常！")
                raise ValueError("这是一个测试异常")
            else:
                print(f"  [FeatureDemo-{self.name}] 正常执行")
                return "成功"

        def get_state(self):
            """获取状态"""
            state = {'name': self.name, 'call_count': self.call_count}
            print(f"  [FeatureDemo-{self.name}] 状态: {state}")
            return state

    print("\n📌 特性 1: 串行执行保证")
    print("   Actor 的方法调用按提交顺序串行执行")
    actor = FeatureDemo.remote("SerialTest")
    time.sleep(0.2)

    # 提交多个操作
    refs = []
    for i in range(3):
        ref = actor.slow_operation.remote(duration=0.1)
        refs.append(ref)
        print(f"  → 提交任务 {i+1}")

    print("  → 等待所有任务完成...")
    results = miniray.get(refs)
    for i, result in enumerate(results):
        print(f"  ✓ 任务 {i+1} 结果: {result}")

    print("\n📌 特性 2: 异常处理")
    print("   Actor 方法抛出的异常会被捕获并返回")

    # 正常调用
    ref1 = actor.handle_error.remote(should_error=False)
    result1 = miniray.get(ref1)
    print(f"  ✓ 正常调用结果: {result1}")

    # 触发异常
    ref2 = actor.handle_error.remote(should_error=True)
    result2 = miniray.get(ref2)
    if isinstance(result2, Exception):
        print(f"  ✓ 捕获到异常: {type(result2).__name__}: {result2}")
    else:
        print(f"  ⚠️  未捕获异常，结果: {result2}")

    print("\n📌 特性 3: 状态持久化")
    print("   Actor 在整个生命周期内保持状态")
    state_ref = actor.get_state.remote()
    state = miniray.get(state_ref)
    print(f"  ✓ Actor 状态: {state}")
    print(f"  ✓ 总共调用了 {state['call_count']} 次方法")

    print("\n📌 关闭 Actor")
    actor.shutdown()
    print("  ✓ Actor 已关闭")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  Mini-Ray Phase 3 - Actor 模型演示")
    print("=" * 60)
    print("\nActor 是 Ray 的核心特性，用于实现有状态的分布式对象")
    print("主要用途：")
    print("  • ML 模型训练和推理（参数服务器、分布式训练）")
    print("  • 有状态计算（计数器、累加器、缓存）")
    print("  • 串行化执行保证（避免竞态条件）")

    # 初始化 Mini-Ray
    print("\n" + "=" * 60)
    print("  初始化 Mini-Ray")
    print("=" * 60)
    miniray.init(num_workers=4)
    time.sleep(0.5)  # 等待 Workers 启动

    try:
        # 运行各个演示
        demo_1_simple_counter()
        demo_2_accumulator()
        demo_3_multiple_actors()
        demo_4_parameter_server()
        demo_5_actor_features()

        # 总结
        print_section("演示完成")
        print("\n✅ 所有 Actor 演示都成功完成！")
        print("\n📊 演示内容回顾:")
        print("  1. 简单计数器 Actor - 基础用法")
        print("  2. 累加器 - 状态管理")
        print("  3. 多 Actor 并发 - 并发控制")
        print("  4. 参数服务器 - ML 应用")
        print("  5. Actor 特性汇总 - 串行执行、异常处理、状态持久化")

        print("\n💡 下一步:")
        print("  • 查看 tests/test_actor.py 了解更多测试用例")
        print("  • 查看 doc/PHASE3_DESIGN.md 了解完整设计")
        print("  • 实现超参数调优框架 (miniray.tune)")

    finally:
        # 关闭 Mini-Ray
        print("\n" + "=" * 60)
        print("  关闭 Mini-Ray")
        print("=" * 60)
        miniray.shutdown()


if __name__ == "__main__":
    main()

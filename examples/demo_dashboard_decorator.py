#!/usr/bin/env python3
"""
完整示例：使用装饰器跟踪 Dashboard 任务

这个脚本演示了如何使用 @track_training_job 装饰器来自动将任务注册到 Dashboard，
展示了侵入性最小的解决方案。
"""
import time
import random
from typing import Dict, Any
import miniray
from miniray.dashboard.tracking import track_training_job, track_inference_job


@track_training_job(
    name="Demo Training Job",
    description="这是一个演示训练任务，用于展示 Dashboard 跟踪功能"
)
def demo_training_task(epochs: int = 5, model_type: str = "neural_network") -> Dict[str, Any]:
    """
    演示训练任务 - 使用装饰器自动跟踪
    
    业务代码完全不变，只需添加 @track_training_job 装饰器
    """
    print(f"[Training] 开始训练 {model_type} 模型，共 {epochs} 个 epoch")
    
    results = {
        'losses': [],
        'accuracies': [],
        'epoch_times': []
    }
    
    for epoch in range(epochs):
        start_time = time.time()
        
        print(f"[Training] Epoch {epoch + 1}/{epochs}")
        
        # 模拟训练过程
        loss = 1.0 - (epoch * 0.15) + random.uniform(-0.05, 0.05)
        accuracy = 0.5 + (epoch * 0.1) + random.uniform(-0.03, 0.03)
        
        results['losses'].append(loss)
        results['accuracies'].append(accuracy)
        
        epoch_time = time.time() - start_time
        results['epoch_times'].append(epoch_time)
        
        print(f"[Training]   Loss: {loss:.4f}, Accuracy: {accuracy:.4f}")
        time.sleep(0.2)  # 模拟实际训练时间
    
    final_accuracy = results['accuracies'][-1]
    print(f"[Training] 训练完成! 最终准确率: {final_accuracy:.4f}")
    
    return {
        'final_accuracy': final_accuracy,
        'avg_loss': sum(results['losses']) / len(results['losses']),
        'epochs_completed': epochs,
        'model_type': model_type
    }


@track_inference_job(
    name="Demo Inference Job", 
    description="演示推理任务跟踪"
)
def demo_inference_task(input_data: list) -> list:
    """
    演示推理任务 - 使用推理专用装饰器
    """
    print(f"[Inference] 开始推理，输入数据点数: {len(input_data)}")
    
    # 模拟推理过程
    results = []
    for i, item in enumerate(input_data):
        # 模拟模型推理 (简单示例：将输入值翻倍)
        result = item * 2 + random.uniform(-0.1, 0.1)
        results.append(result)
        
        if (i + 1) % 10 == 0:  # 每10个打印一次进度
            print(f"[Inference] 完成 {i + 1}/{len(input_data)} 个推理")
        
        time.sleep(0.01)  # 模拟推理时间
    
    print(f"[Inference] 推理完成，输出数据点数: {len(results)}")
    return results


def demonstrate_error_tracking():
    """
    演示错误处理跟踪
    """
    @track_training_job(
        name="Failing Task",
        description="演示失败任务的跟踪"
    )
    def failing_task():
        print("[Failing Task] 开始执行可能失败的任务...")
        time.sleep(1)
        
        # 模拟一个错误
        raise ValueError("模拟训练过程中的错误")
    
    try:
        failing_task()
    except ValueError as e:
        print(f"[Failing Task] 捕获到预期的错误: {e}")
        return str(e)


def demonstrate_remote_integration():
    """
    演示与 Mini-Ray 远程功能的集成
    """
    # 使用远程功能和跟踪功能
    @miniray.remote
    @track_training_job(
        name="Remote Worker Task",
        description="远程工作进程任务"
    )
    def remote_worker_task(task_id: int, data_size: int) -> Dict[str, Any]:
        print(f"[Remote Worker] 执行任务 {task_id}，数据大小: {data_size}")
        
        # 模拟处理时间
        time.sleep(0.5)
        
        # 模拟结果
        result = {
            'task_id': task_id,
            'processed_items': data_size,
            'success_rate': random.uniform(0.8, 0.98),
            'processing_time': 0.5
        }
        
        print(f"[Remote Worker] 任务 {task_id} 完成: {result}")
        return result
    
    print("[Integration] 演示远程任务与 Dashboard 跟踪的集成")
    
    # 初始化 Mini-Ray
    miniray.init(num_workers=2)
    
    try:
        # 提交多个远程任务
        refs = []
        for i in range(3):
            ref = remote_worker_task.remote(i, 100 + i * 50)
            refs.append(ref)
            print(f"[Integration] 提交远程任务 {i}")
        
        # 等待所有任务完成
        results = miniray.get(refs)
        print(f"[Integration] 所有远程任务完成，结果: {results}")
        
    finally:
        miniray.shutdown()


def main():
    """
    主函数 - 运行所有演示
    """
    print("🚀 Mini-Ray Dashboard 装饰器演示")
    print("=" * 80)
    print("使用 @track_training_job 装饰器实现最小侵入性的任务跟踪")
    print("无需修改业务逻辑，只需添加装饰器即可自动跟踪任务")
    print("=" * 80)
    
    # 示例 1: 基本训练任务跟踪
    print("\n📋 示例 1: 基本训练任务跟踪")
    training_result = demo_training_task(epochs=3, model_type="demo_model")
    print(f"训练结果: {training_result}")
    
    # 示例 2: 推理任务跟踪
    print("\n📋 示例 2: 推理任务跟踪")
    inference_result = demo_inference_task(list(range(20)))
    print(f"推理结果样本 (前5个): {inference_result[:5]}")
    
    # 示例 3: 错误处理跟踪
    print("\n📋 示例 3: 错误处理跟踪")
    error_result = demonstrate_error_tracking()
    print(f"错误信息: {error_result}")
    
    # 示例 4: 远程任务集成
    print("\n📋 示例 4: 远程任务与 Dashboard 集成")
    demonstrate_remote_integration()
    
    # 显示 Dashboard 中的所有任务
    print("\n📊 Dashboard 任务统计:")
    from miniray.dashboard.collector import get_collector
    collector = get_collector()
    
    training_jobs = collector.get_training_jobs()
    print(f"  训练任务: {len(training_jobs)} 个")
    
    stats = collector.get_stats()
    print(f"  总统计: {stats}")
    
    print("\n" + "=" * 80)
    print("✅ 所有演示完成!")
    print("💡 要查看 Dashboard，请运行: python -m miniray.dashboard")
    print("   然后访问 http://localhost:8266")
    print("=" * 80)


if __name__ == "__main__":
    exit(main())
"""
miniray 集成测试
测试多个组件协同工作的场景
"""

import pytest
import time
import random


class TestEndToEndWorkflow:
    """端到端工作流测试"""
    
    def test_end_to_end_workflow(self):
        """测试完整的端到端工作流"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def preprocess_data(data_list):
                """预处理数据"""
                return [x * 2 for x in data_list if isinstance(x, int)]

            @miniray.remote
            def process_item(item):
                """处理单个项目"""
                return item ** 2

            @miniray.remote
            def aggregate_results(results):
                """聚合结果"""
                return sum(results)

            # 创建输入数据
            input_data = list(range(1, 6))  # [1, 2, 3, 4, 5]
            
            # 阶段1: 预处理
            preprocessed_ref = preprocess_data.remote(input_data)
            preprocessed_data = miniray.get(preprocessed_ref)
            expected_preprocessed = [2, 4, 6, 8, 10]
            assert preprocessed_data == expected_preprocessed

            # 阶段2: 并行处理
            process_refs = [process_item.remote(x) for x in preprocessed_data]
            processed_results = miniray.get(process_refs)

            # 阶段3: 聚合
            aggregate_ref = aggregate_results.remote(processed_results)
            final_result = miniray.get(aggregate_ref)

            # 验证最终结果: 2² + 4² + 6² + 8² + 10² = 4 + 16 + 36 + 64 + 100 = 220
            expected_final = 220
            assert final_result == expected_final
        finally:
            miniray.shutdown()


class TestParallelProcessing:
    """并行处理测试"""
    
    def test_parallel_processing(self):
        """测试并行处理能力"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def cpu_intensive_task(n):
                """CPU密集型任务"""
                result = 0
                for i in range(n * 1000):
                    result += i % 100
                return result

            # 并行执行多个任务
            task_counts = [100, 200, 300, 400, 500]
            refs = [cpu_intensive_task.remote(n) for n in task_counts]

            # 获取结果
            results = miniray.get(refs)

            # 验证结果数量
            assert len(results) == len(task_counts)
            
            # 验证结果不为None
            for result in results:
                assert result is not None
                assert isinstance(result, int)
        finally:
            miniray.shutdown()


class TestMapReduceSimulation:
    """MapReduce模拟测试"""
    
    def test_map_reduce_simulation(self):
        """模拟MapReduce模式"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def mapper(data_chunk):
                """Mapper函数：计算每个元素的平方"""
                return [x ** 2 for x in data_chunk]

            @miniray.remote
            def reducer(results_chunks):
                """Reducer函数：对所有结果求和"""
                total = 0
                for chunk in results_chunks:
                    total += sum(chunk)
                return total

            # 准备数据
            all_data = list(range(1, 11))  # [1, 2, 3, ..., 10]
            chunk_size = 3
            chunks = [all_data[i:i + chunk_size] for i in range(0, len(all_data), chunk_size)]

            # Map阶段：并行处理每个数据块
            map_refs = [mapper.remote(chunk) for chunk in chunks]
            map_results = miniray.get(map_refs)

            # Reduce阶段：聚合结果
            reduce_ref = reducer.remote(map_results)
            final_result = miniray.get(reduce_ref)

            # 验证：1² + 2² + ... + 10² = 385
            expected = sum(x ** 2 for x in range(1, 11))
            assert final_result == expected
        finally:
            miniray.shutdown()


class TestDistributedComputationWithActors:
    """使用Actor的分布式计算测试"""
    
    def test_distributed_computation_with_actors(self):
        """测试使用Actor的分布式计算"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            class ComputeNode:
                def __init__(self, node_id):
                    self.node_id = node_id
                    self.completed_tasks = 0

                def compute(self, data):
                    """执行计算任务"""
                    self.completed_tasks += 1
                    # 模拟一些计算：对列表中的每个元素求平方和
                    result = sum(x ** 2 for x in data)
                    return {
                        "node_id": self.node_id,
                        "result": result,
                        "input_sum": sum(data)
                    }

                def get_stats(self):
                    return {
                        "node_id": self.node_id,
                        "completed_tasks": self.completed_tasks
                    }

            # 创建多个计算节点
            nodes = [ComputeNode.remote(f"Node-{i}") for i in range(3)]

            # 准备数据并分发到不同节点
            datasets = [
                [1, 2, 3],
                [4, 5, 6], 
                [7, 8, 9]
            ]

            # 在不同节点上并行计算
            compute_refs = []
            for i, dataset in enumerate(datasets):
                node_index = i % len(nodes)  # 循环分配到节点
                ref = nodes[node_index].compute.remote(dataset)
                compute_refs.append(ref)

            # 获取计算结果
            results = miniray.get(compute_refs)

            # 验证结果
            expected_results = [
                {"node_id": "Node-0", "result": 14, "input_sum": 6},   # 1²+2²+3²=14, 1+2+3=6
                {"node_id": "Node-1", "result": 77, "input_sum": 15},  # 4²+5²+6²=77, 4+5+6=15
                {"node_id": "Node-2", "result": 194, "input_sum": 24}  # 7²+8²+9²=194, 7+8+9=24
            ]

            for i, result in enumerate(results):
                assert result["result"] == expected_results[i]["result"]
                assert result["input_sum"] == expected_results[i]["input_sum"]

            # 验证节点统计
            for i, node in enumerate(nodes):
                stats_ref = node.get_stats.remote()
                stats = miniray.get(stats_ref)
                # 每个节点应该处理过至少一个任务
                assert stats["completed_tasks"] >= 1
        finally:
            miniray.shutdown()


class TestErrorRecoveryInWorkflow:
    """工作流中的错误恢复测试"""
    
    def test_error_recovery_in_workflow(self):
        """测试工作流中的错误恢复机制"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def safe_operation(x):
                """安全操作"""
                if x < 0:
                    return 0
                return x * 2

            @miniray.remote
            def batch_processor(items):
                """批量处理器，包含可能的错误恢复"""
                results = []
                for item in items:
                    try:
                        processed = item * 3  # 简单处理
                        results.append(processed)
                    except Exception:
                        results.append(0)  # 错误恢复
                return results

            # 测试安全操作
            refs = [safe_operation.remote(x) for x in [-1, 0, 1, 2]]
            results = miniray.get(refs)
            expected = [0, 0, 2, 4]  # 负数返回0，其他正常处理
            assert results == expected

            # 测试批量处理
            batch_input = [1, 2, 3, 4, 5]
            batch_ref = batch_processor.remote(batch_input)
            batch_results = miniray.get(batch_ref)
            expected_batch = [3, 6, 9, 12, 15]  # 每个元素乘以3
            assert batch_results == expected_batch
        finally:
            miniray.shutdown()


class TestResourceIntensiveTask:
    """资源密集型任务测试"""
    
    def test_resource_intensive_task(self):
        """测试资源密集型任务"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def memory_intensive_task(size):
                """内存密集型任务"""
                # 创建一个大的列表来模拟内存使用
                large_list = list(range(size))
                
                # 对数据进行一些计算
                result = sum(x for x in large_list if x % 2 == 0)  # 只计算偶数
                return {
                    "size": size,
                    "sum_of_evens": result,
                    "count": size // 2 if size % 2 == 0 else (size + 1) // 2
                }

            # 测试中等大小的任务
            result_ref = memory_intensive_task.remote(1000)
            result = miniray.get(result_ref)
            
            assert result["size"] == 1000
            # 验证偶数和的计算：0, 2, 4, ..., 998 的和
            expected_sum = sum(x for x in range(0, 1000, 2))
            assert result["sum_of_evens"] == expected_sum
            assert result["count"] == 500  # 0到999之间的偶数个数
        finally:
            miniray.shutdown()


class TestConcurrentWorkflows:
    """并发工作流测试"""
    
    def test_concurrent_workflows(self):
        """测试并发工作流"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def workflow_a(data):
                """工作流A：数据转换"""
                time.sleep(0.1)  # 模拟处理时间
                return [x * 2 for x in data]

            @miniray.remote
            def workflow_b(data):
                """工作流B：数据聚合"""
                time.sleep(0.1)  # 模拟处理时间
                return sum(data)

            @miniray.remote
            def workflow_c(data):
                """工作流C：数据验证"""
                time.sleep(0.1)  # 模拟处理时间
                return all(x > 0 for x in data)

            # 并发运行不同工作流
            input_data = [1, 2, 3, 4, 5]
            
            ref_a = workflow_a.remote(input_data)  # [2, 4, 6, 8, 10]
            ref_b = workflow_b.remote(input_data)  # 15
            ref_c = workflow_c.remote(input_data)  # True

            results = miniray.get([ref_a, ref_b, ref_c])
            
            assert results[0] == [2, 4, 6, 8, 10]  # workflow_a result
            assert results[1] == 15                # workflow_b result  
            assert results[2] is True              # workflow_c result
        finally:
            miniray.shutdown()


class TestMonteCarloSimulation:
    """蒙特卡洛模拟测试"""
    
    def test_monte_carlo_simulation(self):
        """测试蒙特卡洛模拟"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def estimate_pi_chunk(num_points):
                """估算PI的单个块"""
                inside_circle = 0
                for _ in range(num_points):
                    x = random.random()
                    y = random.random()
                    if x*x + y*y <= 1:
                        inside_circle += 1
                return inside_circle

            # 并行执行多个蒙特卡洛估算
            total_points = 100000
            num_chunks = 10
            points_per_chunk = total_points // num_chunks
            
            refs = [estimate_pi_chunk.remote(points_per_chunk) for _ in range(num_chunks)]
            results = miniray.get(refs)
            
            total_inside = sum(results)
            estimated_pi = 4.0 * total_inside / total_points
            
            # 验证估算的PI值在合理范围内（允许较大误差，因为随机性）
            assert 2.5 < estimated_pi < 3.5
        finally:
            miniray.shutdown()


class TestDataPipeline:
    """数据管道测试"""
    
    def test_data_pipeline(self):
        """测试数据管道"""
        import miniray

        try:
            import miniray._miniray_core as core
            core.cleanup_shared_memory()
        except:
            pass

        miniray.init(num_workers=2)

        try:
            @miniray.remote
            def load_data(size):
                """加载数据"""
                return list(range(size))

            @miniray.remote  
            def transform_data(data, multiplier):
                """转换数据"""
                return [x * multiplier for x in data]

            @miniray.remote
            def filter_data(data, threshold):
                """过滤数据"""
                return [x for x in data if x > threshold]

            @miniray.remote
            def analyze_data(data):
                """分析数据"""
                return {
                    "count": len(data),
                    "sum": sum(data),
                    "avg": sum(data) / len(data) if data else 0,
                    "min": min(data) if data else None,
                    "max": max(data) if data else None
                }

            # 构建数据管道
            # 1. 加载数据
            load_ref = load_data.remote(20)
            raw_data = miniray.get(load_ref)
            
            # 2. 转换数据 (乘以2)
            transform_ref = transform_data.remote(raw_data, 2)
            transformed_data = miniray.get(transform_ref)
            
            # 3. 过滤数据 (只保留大于15的值)
            filter_ref = filter_data.remote(transformed_data, 15)
            filtered_data = miniray.get(filter_ref)
            
            # 4. 分析数据
            analyze_ref = analyze_data.remote(filtered_data)
            analysis = miniray.get(analyze_ref)
            
            # 验证结果
            # 原始数据: [0,1,2,...,19]
            # 转换后: [0,2,4,...,38] (乘以2)
            # 过滤后: [16,18,20,22,24,26,28,30,32,34,36,38] (大于15)
            expected_filtered = list(range(16, 40, 2))
            assert filtered_data == expected_filtered
            
            # 验证分析结果
            assert analysis["count"] == 12  # 16,18,20,22,24,26,28,30,32,34,36,38
            assert analysis["sum"] == sum(expected_filtered)
            assert analysis["avg"] == sum(expected_filtered) / 12
            assert analysis["min"] == 16
            assert analysis["max"] == 38
        finally:
            miniray.shutdown()
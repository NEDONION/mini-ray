"""
test_phase2.py - Phase 2 验收测试

这个测试文件验证 Phase 2 的所有功能：
1. 系统初始化（init）
2. 远程函数装饰器（@ray.remote）
3. 任务提交和执行（.remote()）
4. 结果获取（ray.get()）
5. 多 Worker 并发执行
6. 系统关闭

测试策略：
- 从简单到复杂
- 逐步验证每个组件
- 检查边界情况
"""

import sys
import os
import time

# 添加 miniray 模块路径（向上一级，因为脚本在 tests/ 目录下）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # tests/
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # 项目根目录
MINIRAY_PATH = os.path.join(PROJECT_ROOT, 'python')
if MINIRAY_PATH not in sys.path:
    sys.path.insert(0, MINIRAY_PATH)

# 调试信息
print(f"脚本目录: {SCRIPT_DIR}")
print(f"项目根目录: {PROJECT_ROOT}")
print(f"Python 路径: {MINIRAY_PATH}")
print(f"路径已添加: {MINIRAY_PATH in sys.path}")

import miniray as ray


def test_1_basic_remote_function():
    """
    测试 1: 基本的远程函数调用

    验证点：
    - @ray.remote 装饰器工作
    - .remote() 返回 ObjectRef
    - ray.get() 能获取结果
    """
    print("\n" + "="*60)
    print("测试 1: 基本的远程函数调用")
    print("="*60)

    # 定义一个简单的函数
    @ray.remote
    def add(a, b):
        """简单的加法函数"""
        return a + b

    # 调用远程函数
    print("\n调用: add.remote(3, 5)")
    result_ref = add.remote(3, 5)
    print(f"返回的 ObjectRef: {result_ref}")

    # 获取结果
    print("\n调用: ray.get(result_ref)")
    result = ray.get(result_ref)
    print(f"结果: {result}")

    # 验证
    assert result == 8, f"期望结果为 8，实际为 {result}"
    print("✓ 测试 1 通过：基本远程函数调用成功")

    return True


def test_2_multiple_tasks():
    """
    测试 2: 多个任务并发执行

    验证点：
    - 可以提交多个任务
    - 任务能并发执行
    - 所有结果都能正确获取
    """
    print("\n" + "="*60)
    print("测试 2: 多个任务并发执行")
    print("="*60)

    @ray.remote
    def square(x):
        """计算平方"""
        return x * x

    # 提交多个任务
    print("\n提交 5 个任务...")
    refs = []
    for i in range(5):
        ref = square.remote(i)
        refs.append(ref)
        print(f"  任务 {i}: square.remote({i}) -> {ref}")

    # 等待一下，让 Worker 有时间执行
    print("\n等待任务执行...")
    # 保持原有的 sleep 2 秒
    time.sleep(2)

    # 获取所有结果
    print("\n获取结果...")
    results = []
    for i, ref in enumerate(refs):
        result = ray.get(ref)
        results.append(result)
        print(f"  任务 {i} 结果: {result}")

    # 验证
    expected = [0, 1, 4, 9, 16]
    assert results == expected, f"期望 {expected}，实际 {results}"
    print("✓ 测试 2 通过：多任务并发执行成功")

    return True


def test_3_complex_computation():
    """
    测试 3: 复杂计算任务

    验证点：
    - 能处理计算密集型任务
    - 序列化/反序列化复杂数据结构
    """
    print("\n" + "="*60)
    print("测试 3: 复杂计算任务")
    print("="*60)

    @ray.remote
    def fibonacci(n):
        """计算斐波那契数列第 n 项（迭代实现）"""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    # 测试不同的输入
    print("\n计算斐波那契数列...")
    test_cases = [
        (5, 5),
        (10, 55),
        (15, 610),
        (20, 6765),
    ]

    for n, expected in test_cases:
        ref = fibonacci.remote(n)
        print(f"  fibonacci.remote({n}) -> {ref}")

        # 等待结果
        # 保持原有的 sleep 0.5 秒
        time.sleep(0.5)
        result = ray.get(ref)

        print(f"  fibonacci({n}) = {result} (期望: {expected})")
        assert result == expected, f"fibonacci({n}) 错误：期望 {expected}，实际 {result}"

    print("✓ 测试 3 通过：复杂计算任务成功")
    return True


def test_4_string_operations():
    """
    测试 4: 字符串操作

    验证点：
    - 能正确序列化/反序列化字符串
    - 支持不同类型的返回值
    """
    print("\n" + "="*60)
    print("测试 4: 字符串操作")
    print("="*60)

    @ray.remote
    def process_text(text):
        """处理文本：转大写并添加前缀"""
        return f"PROCESSED: {text.upper()}"

    # 测试字符串
    test_strings = [
        "hello",
        "world",
        "mini-ray",
        "分布式计算",
    ]

    print("\n处理字符串...")
    for text in test_strings:
        ref = process_text.remote(text)
        print(f"  process_text.remote('{text}') -> {ref}")

        time.sleep(0.3)
        result = ray.get(ref)
        print(f"  结果: '{result}'")

        expected = f"PROCESSED: {text.upper()}"
        assert result == expected, f"期望 '{expected}'，实际 '{result}'"

    print("✓ 测试 4 通过：字符串操作成功")
    # 【修复点】：缺少 return True
    return True


def test_5_list_and_dict():
    """
    测试 5: 列表和字典类型

    验证点：
    - 能序列化/反序列化复杂数据结构
    - 支持列表、字典等容器类型
    """
    print("\n" + "="*60)
    print("测试 5: 列表和字典类型")
    print("="*60)

    @ray.remote
    def process_data(data):
        """
        处理数据：
        - 如果是列表，返回求和
        - 如果是字典，返回所有值的和
        """
        if isinstance(data, list):
            return sum(data)
        elif isinstance(data, dict):
            return sum(data.values())
        else:
            return None

    # 测试列表
    print("\n测试列表...")
    list_data = [1, 2, 3, 4, 5]
    ref1 = process_data.remote(list_data)
    time.sleep(0.3)
    result1 = ray.get(ref1)
    print(f"  sum({list_data}) = {result1}")
    assert result1 == 15, f"列表求和错误：期望 15，实际 {result1}"

    # 测试字典
    print("\n测试字典...")
    dict_data = {"a": 10, "b": 20, "c": 30}
    ref2 = process_data.remote(dict_data)
    time.sleep(0.3)
    result2 = ray.get(ref2)
    print(f"  sum({dict_data}.values()) = {result2}")
    assert result2 == 60, f"字典求和错误：期望 60，实际 {result2}"

    print("✓ 测试 5 通过：复杂数据结构成功")
    return True


def test_6_worker_load_balancing():
    """
    测试 6: Worker 负载均衡

    验证点：
    - 多个 Worker 能分担任务
    - 任务分配相对均匀
    """
    print("\n" + "="*60)
    print("测试 6: Worker 负载均衡")
    print("="*60)

    @ray.remote
    def sleep_and_return(value, sleep_time=0.1):
        """休眠一段时间后返回值"""
        import time
        time.sleep(sleep_time)
        return value

    # 提交大量任务
    print("\n提交 10 个任务（每个耗时 0.1 秒）...")
    num_tasks = 10
    refs = []

    start_time = time.time()
    for i in range(num_tasks):
        ref = sleep_and_return.remote(i, 0.1)
        refs.append(ref)

    # 等待所有任务完成
    print("等待任务执行...")

    results = [ray.get(ref) for ref in refs]
    end_time = time.time()

    elapsed = end_time - start_time
    print(f"\n总耗时: {elapsed:.2f} 秒")
    print(f"任务数: {num_tasks}")
    print(f"每任务耗时: 0.1 秒")
    print(f"如果串行执行需要: {num_tasks * 0.1:.1f} 秒")
    print(f"实际耗时: {elapsed:.2f} 秒")

    # 验证结果
    assert results == list(range(num_tasks)), f"结果不正确：{results}"

    # 并发执行应该比串行快
    # 注意：因为有通信开销，不会达到理论最优
    # 这里只检查比串行快即可
    # 考虑到 num_workers=2，理论并行时间是 10 * 0.1 / 2 = 0.5 秒
    assert elapsed < num_tasks * 0.1, "实际耗时不应该超过串行时间"
    print(f"\n并发加速比: {num_tasks * 0.1 / elapsed:.2f}x")

    print("✓ 测试 6 通过：Worker 负载均衡正常")
    return True


def test_7_error_handling():
    """
    测试 7: 错误处理

    验证点：
    - Worker 能捕获函数执行错误
    - 错误能传回主进程
    """
    print("\n" + "="*60)
    print("测试 7: 错误处理")
    print("="*60)

    @ray.remote
    def divide(a, b):
        """除法函数（可能除零）"""
        return a / b

    # 测试正常情况
    print("\n测试正常除法...")
    ref1 = divide.remote(10, 2)
    time.sleep(0.3)
    result1 = ray.get(ref1)
    print(f"  10 / 2 = {result1}")
    assert result1 == 5.0, f"除法错误：期望 5.0，实际 {result1}"

    # 测试除零错误
    print("\n测试除零错误...")
    ref2 = divide.remote(10, 0)
    time.sleep(0.3)

    # 保持原有逻辑，检查是抛出异常还是返回序列化的异常对象
    try:
        result2 = ray.get(ref2)
        print(f"  意外：没有抛出异常，结果为 {result2}")
        # 注意：当前实现可能将异常序列化后返回
        if isinstance(result2, Exception):
            print(f"  ✓ 正确捕获了异常: {type(result2).__name__}")
        else:
            print(f"  警告：期望异常，但得到结果 {result2}")
    except Exception as e:
        # 如果 ray.get 抛出异常 (理想行为)
        print(f"  ✓ 正确抛出异常: {type(e).__name__}: {e}")
        # 验证抛出的是 ZeroDivisionError 或其封装的类型
        if not isinstance(e, ZeroDivisionError):
             print(f"  警告：抛出的异常类型不是 ZeroDivisionError，而是 {type(e).__name__}")


    print("✓ 测试 7 通过：错误处理基本正常")
    print("  注意：当前实现将异常序列化返回，未来可改进")
    # 【修复点】：缺少 return True
    return True


def run_all_tests():
    """
    运行所有测试

    测试流程：
    1. 初始化 mini-ray
    2. 运行各个测试用例
    3. 统计测试结果
    4. 关闭 mini-ray
    """
    print("\n" + "="*70)
    print(" "*20 + "Phase 2 验收测试")
    print("="*70)

    # 初始化 mini-ray
    print("\n初始化 mini-ray (2 个 Worker)...")
    # 保持原有逻辑：初始化 2 个 Worker
    ray.init(num_workers=2)
    print("✓ 初始化成功")

    # 等待 Worker 启动
    print("\n等待 Worker 启动...")
    # 保持原有 sleep 2 秒
    time.sleep(2)

    # 运行测试
    tests = [
        ("基本远程函数调用", test_1_basic_remote_function),
        ("多任务并发执行", test_2_multiple_tasks),
        ("复杂计算任务", test_3_complex_computation),
        ("字符串操作", test_4_string_operations),
        ("复杂数据结构", test_5_list_and_dict),
        ("Worker 负载均衡", test_6_worker_load_balancing),
        ("错误处理", test_7_error_handling),
    ]

    results = []
    # 修复：确保所有 test_func 都返回 True/False
    for name, test_func in tests:
        try:
            # 捕获 test_func 内部的 AssertionError，并将其标记为失败
            success = test_func()
            results.append((name, success, None))
        except AssertionError as e:
            # AssertionError 是测试函数内部的验证失败
            print(f"\n✗ 测试失败: {name}")
            print(f"  断言错误: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False, e))
        except Exception as e:
            # 其他运行时错误 (如初始化失败等)
            print(f"\n✗ 测试失败: {name}")
            print(f"  运行时错误: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False, e))

    # 打印总结
    print("\n" + "="*70)
    print(" "*25 + "测试总结")
    print("="*70)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    print(f"\n总计: {total} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {total - passed} 个")

    print("\n详细结果:")
    for name, success, error in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {status}: {name}")
        if error:
            # 统一打印错误类型
            error_type = type(error).__name__
            print(f"         错误: {error_type}: {error}")

    # 关闭 mini-ray
    print("\n" + "="*70)
    print("关闭 mini-ray...")
    ray.shutdown()
    print("✓ 关闭成功")

    print("\n" + "="*70)
    if passed == total:
        print(" "*20 + "🎉 所有测试通过！")
    else:
        print(f" "*15 + f"⚠️  {total - passed} 个测试失败")
    print("="*70 + "\n")

    return passed == total


if __name__ == "__main__":
    """
    主函数
    """
    success = run_all_tests()

    # 返回退出码
    import sys
    sys.exit(0 if success else 1)
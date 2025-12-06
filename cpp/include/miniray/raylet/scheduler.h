/**
 * scheduler.h - 分布式任务调度器
 *
 * ============================================================
 * 设计思想和架构
 * ============================================================
 *
 * Scheduler 是 Mini-Ray 的调度中心，负责：
 * 1. 接收任务提交请求
 * 2. 维护任务队列
 * 3. 分发任务给 Worker
 * 4. 管理 Worker 状态
 *
 * 类比 Ray 的设计：
 * - Ray: Raylet (GCS + Scheduler + Object Manager)
 * - Mini-Ray: Scheduler (简化版，仅任务调度)
 *
 * ============================================================
 * 调度策略
 * ============================================================
 *
 * 当前实现：简单队列（FIFO）
 * - 任务按提交顺序执行
 * - Worker 拉取模式（Pull-based）
 *
 * 生产系统的调度策略：
 * 1. 优先级调度
 *    - 高优先级任务先执行
 *    - 避免饥饿（aging）
 *
 * 2. 数据局部性
 *    - 优先分配给已有输入数据的 Worker
 *    - 减少网络传输
 *
 * 3. 负载均衡
 *    - 考虑 Worker 的当前负载
 *    - 避免热点
 *
 * 4. 资源感知
 *    - 考虑 CPU、内存、GPU 需求
 *    - 资源匹配
 *
 * Mini-Ray 采用最简单的 FIFO + Pull-based 策略
 *
 * ============================================================
 * 队列实现：循环队列
 * ============================================================
 *
 * 为什么用循环队列？
 * - 固定大小，避免动态分配
 * - O(1) 插入和删除
 * - 适合共享内存
 *
 * 循环队列原理：
 * ```
 * 初始状态：head=0, tail=0, count=0
 * [empty][empty][empty][empty]
 *  ^head
 *  ^tail
 *
 * 插入 A：tail=(tail+1)%MAX, count++
 * [A][empty][empty][empty]
 *  ^head
 *     ^tail
 *
 * 插入 B, C：
 * [A][B][C][empty]
 *  ^head
 *           ^tail
 *
 * 取出 A：head=(head+1)%MAX, count--
 * [A][B][C][empty]
 *     ^head
 *           ^tail
 *
 * 插入 D, E：
 * [E][B][C][D]
 *     ^head
 *  ^tail (循环回来了！)
 * ```
 *
 * 判断队列状态：
 * - 空：count == 0
 * - 满：count == MAX
 * - 不使用 head == tail 判断（歧义）
 *
 * ============================================================
 * 任务序列化策略
 * ============================================================
 *
 * Python 函数不能直接存储在 C++ 中，需要序列化：
 * 1. Python 端使用 pickle/cloudpickle 序列化
 * 2. C++ 端以二进制数据存储
 * 3. Worker 端反序列化执行
 *
 * SharedTask 结构：
 * - task_id, function_id: 元数据
 * - return_ref: 返回值的 ObjectRef
 * - serialized_function: pickle 后的函数体
 * - serialized_args: pickle 后的参数
 *
 * 为什么分开存储函数和参数？
 * - 相同函数可以复用（未来优化）
 * - 更清晰的语义
 *
 * ============================================================
 * Worker 状态管理
 * ============================================================
 *
 * WorkerInfo 记录每个 Worker 的状态：
 * - worker_id: 唯一标识
 * - is_idle: 是否空闲（原子操作）
 *
 * Worker 生命周期：
 * 1. RegisterWorker: Worker 启动时注册
 * 2. MarkWorkerBusy: 开始执行任务
 * 3. MarkWorkerIdle: 任务完成
 * 4. UnregisterWorker: Worker 退出
 *
 * 为什么要 padding？
 * - 避免伪共享（false sharing）
 * - 确保每个 WorkerInfo 在独立的缓存行
 *
 * ============================================================
 * 深拷贝 vs 浅拷贝
 * ============================================================
 *
 * SharedTask 中的数据是固定大小数组（栈上）：
 * - serialized_function[MAX_SIZE]
 * - serialized_args[MAX_SIZE]
 *
 * Task 中的数据是动态数组（堆上）：
 * - std::vector<uint8_t> serialized_function
 * - std::vector<uint8_t> serialized_args
 *
 * FromTask: vector → 固定数组（深拷贝）
 * ToTask: 固定数组 → vector（深拷贝）
 *
 * 为什么要拷贝？
 * - 共享内存不能存储指针（不同进程地址空间不同）
 * - vector 内部是指针，无法直接共享
 * - 必须拷贝实际数据
 *
 * ============================================================
 * C++ 特性运用
 * ============================================================
 *
 * 1. std::fprintf vs std::cout
 *    - fprintf 更底层，直接写文件描述符
 *    - 适合调试多进程程序
 *    - std::cout 可能有缓冲问题
 *
 * 2. std::fflush
 *    - 强制刷新缓冲区
 *    - 确保立即输出（调试用）
 *
 * 3. const 成员函数
 *    - 不修改对象状态
 *    - 编译器检查
 */

#pragma once

#include "miniray/common/memory.h"
#include "miniray/common/task.h"
#include <atomic>
#include <memory>
#include <iostream>
#include <cstdio>
#include <cstring>
#include <stdexcept>

namespace miniray {
namespace raylet {

/**
 * @brief 调度器的共享内存布局
 *
 * 该结构体定义了调度器在共享内存中的数据组织方式
 */
struct SchedulerLayout {
    /**
     * @brief 头部元数据
     *
     * 包含队列状态和同步原语
     */
    struct Header {
        common::ProcessMutex mutex;       ///< 保护整个调度器的锁
        std::atomic<int> task_count;      ///< 当前任务数（队列长度）
        std::atomic<int> head;            ///< 队列头（读取位置）
        std::atomic<int> tail;            ///< 队列尾（写入位置）
        char padding[64];                 ///< 缓存行填充
    } header;

    // 任务队列配置
    static constexpr int MAX_TASKS = 100;                      ///< 最大任务数
    static constexpr int MAX_SERIALIZED_SIZE = 64 * 1024;      ///< 单个序列化字段最大 64KB

    /**
     * @brief 共享内存中的任务表示
     *
     * 与 Task 的区别：
     * - Task: 使用 std::vector（堆分配）
     * - SharedTask: 使用固定大小数组（栈分配）
     *
     * 为什么要转换？
     * - 共享内存不能包含指针
     * - vector 内部是指针，不同进程看到的地址不同
     */
    struct SharedTask {
        TaskID task_id;                                  ///< 任务 ID
        FunctionID function_id;                          ///< 函数 ID
        ObjectRef return_ref;                            ///< 返回值引用

        size_t serialized_function_size;                 ///< 函数序列化数据大小
        uint8_t serialized_function[MAX_SERIALIZED_SIZE]; ///< 函数序列化数据

        size_t serialized_args_size;                     ///< 参数序列化数据大小
        uint8_t serialized_args[MAX_SERIALIZED_SIZE];    ///< 参数序列化数据

        /**
         * @brief 默认构造函数
         */
        SharedTask() : serialized_function_size(0), serialized_args_size(0) {}

        /**
         * @brief 从 Task 拷贝到 SharedTask
         *
         * @param task 源任务（包含 vector）
         *
         * 过程：
         * 1. 拷贝元数据（ID、ref）
         * 2. 检查序列化数据大小
         * 3. 使用 memcpy 拷贝序列化数据
         *
         * 为什么用 memcpy？
         * - vector::data() 返回底层数组指针
         * - uint8_t 是 POD 类型，可安全 memcpy
         * - 比循环赋值快得多
         */
        void FromTask(const Task& task);

        /**
         * @brief 从 SharedTask 拷贝到 Task
         *
         * @param task 目标任务（包含 vector）
         *
         * 过程：
         * 1. 拷贝元数据
         * 2. 使用 vector::assign 拷贝序列化数据
         *
         * vector::assign vs memcpy：
         * - assign 自动管理 vector 的容量
         * - 更符合 C++ 风格
         * - 异常安全
         */
        void ToTask(Task& task) const;
    };

    SharedTask tasks[MAX_TASKS];  ///< 任务队列（循环队列）

    // Worker 管理
    static constexpr int MAX_WORKERS = 16;  ///< 最大 Worker 数

    /**
     * @brief Worker 信息
     *
     * 记录每个 Worker 的状态
     */
    struct WorkerInfo {
        int worker_id;                ///< Worker ID（-1 表示未使用）
        std::atomic<bool> is_idle;    ///< 是否空闲
        char padding[56];             ///< 缓存行对齐（64 - 4 - 1 - 3(对齐) = 56）
    } workers[MAX_WORKERS];

    /**
     * @brief 计算总共需要的共享内存大小
     */
    static constexpr size_t TotalSize() {
        return sizeof(SchedulerLayout);
    }
};

/**
 * @brief 共享内存调度器
 *
 * 封装任务调度的所有操作
 *
 * 线程安全性：
 * - 所有公有方法都是进程安全的
 * - 使用 ProcessMutex 保护共享状态
 *
 * 使用示例：
 * ```cpp
 * // Driver 进程
 * Scheduler scheduler(true);
 * Task task = ...;
 * scheduler.SubmitTask(task);
 *
 * // Worker 进程
 * Scheduler scheduler(false);
 * scheduler.RegisterWorker(worker_id);
 * auto task = scheduler.GetNextTask();
 * // 执行任务...
 * scheduler.MarkWorkerIdle(worker_id);
 * ```
 */
class Scheduler {
public:
    /**
     * @brief 构造函数
     *
     * @param create true=创建新调度器，false=连接已存在的
     *
     * 初始化：
     * 1. 创建/打开共享内存
     * 2. 获取 SchedulerLayout 指针
     * 3. 如果是创建模式：
     *    - 初始化 mutex
     *    - 初始化队列状态（count=0, head=0, tail=0）
     *    - 初始化所有 Worker 为未使用状态
     */
    explicit Scheduler(bool create = true);

    /**
     * @brief 析构函数
     *
     * 使用默认析构（RAII 自动清理）
     */
    ~Scheduler() = default;

    /**
     * @brief 提交任务
     *
     * @param task 待提交的任务
     *
     * 算法：
     * 1. 打印调试信息（函数和参数大小）
     * 2. 加锁
     * 3. 检查队列是否已满
     * 4. 将 Task 拷贝到 tail 位置的 SharedTask
     * 5. tail = (tail + 1) % MAX_TASKS（循环）
     * 6. task_count++
     *
     * 时间复杂度：O(n)，n 为序列化数据大小（memcpy）
     *
     * 异常：如果队列已满，抛出 runtime_error
     */
    void SubmitTask(const Task& task);

    /**
     * @brief 获取下一个任务
     *
     * @return 任务指针（shared_ptr），如果队列为空则返回 nullptr
     *
     * 算法：
     * 1. 加锁
     * 2. 检查队列是否为空
     * 3. 从 head 位置读取 SharedTask
     * 4. 在堆上分配 Task 对象
     * 5. 将 SharedTask 拷贝到 Task
     * 6. head = (head + 1) % MAX_TASKS
     * 7. task_count--
     *
     * 为什么返回 shared_ptr？
     * - Task 对象可能很大（序列化数据）
     * - shared_ptr 自动管理生命周期
     * - 可以安全传递给调用者
     *
     * 为什么在堆上分配？
     * - Task 包含 vector，生命周期需要超出函数
     * - shared_ptr 自动释放
     *
     * 时间复杂度：O(n)，n 为序列化数据大小
     */
    std::shared_ptr<Task> GetNextTask();

    /**
     * @brief 注册 Worker
     *
     * @param worker_id Worker 的唯一标识
     *
     * 算法：
     * 1. 加锁
     * 2. 查找空闲槽位（worker_id == -1）
     * 3. 记录 worker_id
     * 4. 标记为 idle
     *
     * 异常：如果 Worker 槽位已满，抛出 runtime_error
     */
    void RegisterWorker(int worker_id);

    /**
     * @brief 注销 Worker
     *
     * @param worker_id Worker 的唯一标识
     *
     * 算法：
     * 1. 加锁
     * 2. 查找对应的 worker_id
     * 3. 标记为未使用（worker_id = -1）
     */
    void UnregisterWorker(int worker_id);

    /**
     * @brief 标记 Worker 为忙碌
     *
     * @param worker_id Worker 的唯一标识
     *
     * 用途：Worker 开始执行任务时调用
     *
     * 注意：没有加锁（原子操作足够）
     */
    void MarkWorkerBusy(int worker_id);

    /**
     * @brief 标记 Worker 为空闲
     *
     * @param worker_id Worker 的唯一标识
     *
     * 用途：Worker 完成任务时调用
     *
     * 注意：没有加锁（原子操作足够）
     */
    void MarkWorkerIdle(int worker_id);

    /**
     * @brief 获取待处理任务数
     *
     * @return 当前队列中的任务数
     *
     * 原子操作，不需要加锁
     */
    size_t GetPendingTaskCount() const;

    /**
     * @brief 获取空闲 Worker 数
     *
     * @return 空闲的 Worker 数量
     *
     * 算法：
     * 1. 遍历所有 Worker
     * 2. 统计 worker_id != -1 且 is_idle == true 的数量
     *
     * 注意：没有加锁（非关键路径，允许轻微不一致）
     */
    size_t GetIdleWorkerCount() const;

    /**
     * @brief 检查是否有空闲 Worker
     *
     * @return true=有空闲，false=全忙
     *
     * 快捷方法，等价于 GetIdleWorkerCount() > 0
     */
    bool HasIdleWorker() const;

    /**
     * @brief 清理共享内存
     *
     * 静态方法，删除调度器的共享内存对象
     */
    static void Cleanup();

private:
    common::SharedMemory shm_;       ///< 共享内存管理器
    SchedulerLayout* layout_;        ///< 指向共享内存布局的指针
};

}  // namespace raylet
}  // namespace miniray

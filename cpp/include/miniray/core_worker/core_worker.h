/**
 * core_worker.h - CoreWorker 核心工作器
 *
 * ============================================================
 * 设计思想和架构
 * ============================================================
 *
 * CoreWorker 是 Mini-Ray Worker 进程的核心组件，负责：
 * 1. 任务提交（Driver 角色）
 * 2. 任务获取和执行（Worker 角色）
 * 3. 对象存储交互
 * 4. 状态管理
 *
 * 类比 Ray 的设计：
 * - Ray: CoreWorker 是复杂的 C++ 类，包含所有 Worker 逻辑
 * - Mini-Ray: 简化版，仅封装 Scheduler 和 ObjectStore
 *
 * ============================================================
 * 设计模式：Facade（外观）模式
 * ============================================================
 *
 * CoreWorker 是一个 Facade，隐藏了底层复杂性：
 *
 * 客户端视角（简单）：
 * ```cpp
 * CoreWorker worker(...);
 * worker.SubmitTask(task);      // 简单！
 * auto obj = worker.GetObject(ref);
 * ```
 *
 * 实际内部（复杂）：
 * ```cpp
 * worker.SubmitTask(task) {
 *     scheduler_->SubmitTask(task);  // 与调度器交互
 *     // 可能还有日志、监控、重试...
 * }
 * ```
 *
 * Facade 的优势：
 * 1. 简化接口：客户端不需要知道 Scheduler/ObjectStore 的存在
 * 2. 解耦：可以更换底层实现而不影响客户端
 * 3. 统一入口：所有 Worker 操作都通过 CoreWorker
 *
 * ============================================================
 * 设计模式：依赖注入（Dependency Injection）
 * ============================================================
 *
 * CoreWorker 不自己创建 Scheduler 和 ObjectStore，而是通过构造函数注入：
 *
 * ❌ 不好的设计（紧耦合）：
 * ```cpp
 * CoreWorker::CoreWorker() {
 *     scheduler_ = new Scheduler(true);
 *     object_store_ = new ObjectStore(true);
 * }
 * ```
 * 问题：
 * - 无法测试（无法注入 mock）
 * - 无法复用已有实例
 * - 无法配置参数
 *
 * ✅ 好的设计（依赖注入）：
 * ```cpp
 * CoreWorker::CoreWorker(
 *     shared_ptr<Scheduler> scheduler,
 *     shared_ptr<ObjectStore> object_store,
 *     int worker_id)
 * ```
 * 优势：
 * - 可测试：注入 MockScheduler
 * - 灵活：多个 CoreWorker 可共享同一个 Scheduler
 * - 清晰：依赖关系显式声明
 *
 * ============================================================
 * C++ 智能指针：shared_ptr vs unique_ptr
 * ============================================================
 *
 * shared_ptr（共享所有权）：
 * - 引用计数：多个 shared_ptr 可指向同一对象
 * - 最后一个 shared_ptr 销毁时，对象被删除
 * - 线程安全：引用计数操作是原子的
 * - 开销：额外的控制块、原子操作
 *
 * unique_ptr（独占所有权）：
 * - 只能有一个 unique_ptr 指向对象
 * - unique_ptr 销毁时，对象被删除
 * - 不可拷贝，但可移动
 * - 零开销：与裸指针性能相同
 *
 * CoreWorker 为什么用 shared_ptr？
 * - Scheduler 和 ObjectStore 可能被多个 Worker 共享
 * - 例如：多个 Worker 进程连接同一个共享内存调度器
 *
 * ============================================================
 * C++ 参数传递：传值 vs 传引用
 * ============================================================
 *
 * 智能指针参数的最佳实践：
 *
 * ❌ 不推荐：const shared_ptr<T>&
 * ```cpp
 * CoreWorker(const shared_ptr<Scheduler>& scheduler)
 *     : scheduler_(scheduler) {}  // 拷贝，增加引用计数
 * ```
 * 问题：传引用是为了避免拷贝，但初始化列表仍然拷贝
 *
 * ✅ 推荐：shared_ptr<T>（传值）+ std::move
 * ```cpp
 * CoreWorker(shared_ptr<Scheduler> scheduler)
 *     : scheduler_(std::move(scheduler)) {}  // 移动，不增加引用计数
 * ```
 * 优势：
 * - 调用方可以选择拷贝或移动
 * - 初始化列表中移动，避免引用计数操作
 * - 语义清晰：所有权转移
 *
 * 例子：
 * ```cpp
 * auto sched = make_shared<Scheduler>(true);
 * CoreWorker w1(sched);           // 拷贝，引用计数 = 2
 * CoreWorker w2(std::move(sched)); // 移动，引用计数 = 2，sched = nullptr
 * ```
 *
 * ============================================================
 * inline 函数
 * ============================================================
 *
 * inline 关键字建议编译器内联展开函数：
 *
 * 非内联：
 * ```cpp
 * int GetWorkerID() const { return worker_id_; }
 * ```
 * 编译后：
 * ```asm
 * call GetWorkerID  ; 函数调用开销
 * mov eax, [rdi+16] ; 读取 worker_id_
 * ret
 * ```
 *
 * 内联：
 * ```cpp
 * inline int GetWorkerID() const { return worker_id_; }
 * ```
 * 编译后：
 * ```asm
 * mov eax, [rdi+16] ; 直接读取，无函数调用
 * ```
 *
 * 何时使用 inline？
 * - 简单的 getter/setter
 * - 函数体很小（1-2 行）
 * - 性能关键路径
 *
 * 注意：
 * - inline 只是建议，编译器可能不采纳
 * - 现代编译器会自动内联（不需要显式 inline）
 * - 过度内联会导致代码膨胀
 *
 * ============================================================
 * 禁用拷贝构造和赋值
 * ============================================================
 *
 * 为什么禁用 CoreWorker 的拷贝？
 *
 * CoreWorker 代表一个唯一的 Worker 实体：
 * - worker_id_ 是唯一的
 * - 拷贝会产生两个相同 ID 的 Worker（错误！）
 * - 应该通过指针/引用传递
 *
 * C++11 之前（不推荐）：
 * ```cpp
 * private:
 *     CoreWorker(const CoreWorker&);  // 声明但不定义
 *     CoreWorker& operator=(const CoreWorker&);
 * ```
 *
 * C++11 之后（推荐）：
 * ```cpp
 * CoreWorker(const CoreWorker&) = delete;
 * CoreWorker& operator=(const CoreWorker&) = delete;
 * ```
 *
 * 优势：
 * - 编译时错误（而非链接时）
 * - 更清晰的意图表达
 * - 更好的错误信息
 *
 * ============================================================
 * 类的职责（Single Responsibility Principle）
 * ============================================================
 *
 * CoreWorker 的职责：
 * 1. 封装 Scheduler 和 ObjectStore
 * 2. 提供统一的 Worker API
 * 3. 管理 Worker 状态（ID、忙闲）
 *
 * CoreWorker 不负责：
 * - 任务序列化（Task 的职责）
 * - 共享内存管理（Scheduler/ObjectStore 的职责）
 * - Worker 进程管理（Python 层的职责）
 *
 * 清晰的职责划分：
 * - 易于理解
 * - 易于测试
 * - 易于维护
 */

#pragma once

#include <memory>
#include "miniray/common/buffer.h"
#include "miniray/raylet/scheduler.h"
#include "miniray/object_store/object_store.h"
#include "miniray/common/task.h"
#include "miniray/common/object_ref.h"

namespace miniray {
namespace core_worker {

/**
 * @brief CoreWorker - Worker 进程的核心组件
 *
 * 封装了任务调度和对象存储的所有交互
 *
 * 使用示例（Driver）：
 * ```cpp
 * auto scheduler = make_shared<Scheduler>(true);
 * auto store = make_shared<ObjectStore>(true);
 * CoreWorker worker(scheduler, store, 0);
 *
 * Task task = ...;
 * ObjectRef ref = worker.SubmitTask(task);
 * auto result = worker.GetObject(ref);
 * ```
 *
 * 使用示例（Worker）：
 * ```cpp
 * auto scheduler = make_shared<Scheduler>(false);
 * auto store = make_shared<ObjectStore>(false);
 * CoreWorker worker(scheduler, store, worker_id);
 *
 * while (true) {
 *     auto task = worker.GetNextTask();
 *     if (!task) break;
 *     // 执行任务...
 *     worker.PutObject(task->return_ref, result);
 * }
 * ```
 */
class CoreWorker {
public:
    /**
     * @brief 构造函数
     *
     * @param scheduler 调度器（共享所有权）
     * @param object_store 对象存储（共享所有权）
     * @param worker_id Worker 唯一标识
     *
     * 设计细节：
     * - 使用智能指针传值 + std::move
     * - 明确表达所有权语义
     * - 避免不必要的引用计数操作
     *
     * 为什么传值而非 const&？
     * 参见文件头部的详细解释
     */
    CoreWorker(
        std::shared_ptr<raylet::Scheduler> scheduler,
        std::shared_ptr<object_store::ObjectStore> object_store,
        int worker_id);

    /**
     * @brief 析构函数
     *
     * 使用默认析构：
     * - shared_ptr 自动管理生命周期
     * - 不需要手动释放资源
     */
    ~CoreWorker() = default;

    // 禁止拷贝（Worker 是唯一实体）
    CoreWorker(const CoreWorker&) = delete;
    CoreWorker& operator=(const CoreWorker&) = delete;

    /**
     * @brief 提交任务
     *
     * @param task 待提交的任务
     * @return 任务返回值的 ObjectRef
     *
     * 流程：
     * 1. 将任务提交到调度器
     * 2. 返回任务的 return_ref
     *
     * 注意：
     * - 任务的 return_ref 应该在提交前创建
     * - 调用方可以立即使用 return_ref（但可能阻塞在 Get）
     */
    ObjectRef SubmitTask(const Task& task);

    /**
     * @brief 获取下一个待执行任务
     *
     * @return 任务指针，如果队列为空则返回 nullptr
     *
     * 用途：Worker 主循环中轮询任务
     *
     * 典型用法：
     * ```cpp
     * while (running) {
     *     auto task = worker.GetNextTask();
     *     if (task) {
     *         ExecuteTask(*task);
     *     } else {
     *         sleep(100ms);  // 短暂休眠，避免忙等待
     *     }
     * }
     * ```
     */
    std::shared_ptr<Task> GetNextTask();

    /**
     * @brief 存储对象
     *
     * @param object_ref 对象引用（已包含 ObjectID）
     * @param data 对象数据
     *
     * 用途：
     * - Worker 存储任务返回值
     * - Driver 存储输入参数
     *
     * 注意：
     * - object_ref 应该提前创建（避免竞态）
     * - data 会被拷贝到共享内存
     */
    void PutObject(const ObjectRef& object_ref, const std::vector<uint8_t>& data);

    /**
     * @brief 获取对象
     *
     * @param object_ref 对象引用
     * @return 对象数据（Buffer）
     *
     * 注意：
     * - 如果对象不存在，会抛出异常
     * - 当前实现不支持等待（未来可添加）
     */
    std::shared_ptr<Buffer> GetObject(const ObjectRef& object_ref);

    /**
     * @brief 获取 Worker ID
     *
     * @return Worker 的唯一标识
     *
     * inline 函数：
     * - 编译器可能内联展开
     * - 避免函数调用开销
     * - 适合简单的 getter
     */
    inline int GetWorkerID() const {
        return worker_id_;
    }

    /**
     * @brief 标记 Worker 为忙碌
     *
     * 用途：Worker 开始执行任务时调用
     */
    void MarkWorkerBusy();

    /**
     * @brief 标记 Worker 为空闲
     *
     * 用途：Worker 完成任务时调用
     */
    void MarkWorkerIdle();

private:
    std::shared_ptr<raylet::Scheduler> scheduler_;           ///< 调度器（共享）
    std::shared_ptr<object_store::ObjectStore> object_store_; ///< 对象存储（共享）
    int worker_id_;                                           ///< Worker ID
};

}  // namespace core_worker
}  // namespace miniray

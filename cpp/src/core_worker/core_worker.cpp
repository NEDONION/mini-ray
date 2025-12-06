/**
 * core_worker.cpp - CoreWorker 类的实现
 *
 * ============================================================
 * C++ 高级语法和最佳实践
 * ============================================================
 *
 * 1. 构造函数初始化列表
 *    语法：Constructor(...) : member1_(value1), member2_(value2) {}
 *    优势：
 *    - 直接初始化，避免先默认构造再赋值
 *    - 对于 const 成员和引用成员，必须使用初始化列表
 *    - 初始化顺序与成员声明顺序一致（非列表顺序）
 *    最佳实践：始终使用初始化列表
 *
 * 2. std::move 移动语义
 *    将左值转换为右值引用
 *    触发移动构造/赋值而非拷贝
 *    好处：
 *    - 避免不必要的拷贝
 *    - 对于管理资源的类（智能指针、容器）性能提升明显
 *    注意：move 后的对象处于有效但未指定的状态
 *    最佳实践：
 *    - 局部变量返回时不要 move（编译器会自动优化）
 *    - 参数传递到成员变量时使用 move
 *
 * 3. -> 运算符
 *    指针成员访问运算符
 *    ptr->member 等价于 (*ptr).member
 *    适用于裸指针和智能指针
 */

#include "miniray/core_worker/core_worker.h"

namespace miniray {
namespace core_worker {

/**
 * @brief CoreWorker 构造函数实现
 *
 * 初始化列表 + std::move 的最佳实践：
 *
 * std::move 将参数转为右值，触发 shared_ptr 的移动构造
 * - 移动构造：转移所有权，不增加引用计数
 * - 拷贝构造：共享所有权，增加引用计数
 *
 * 例子：
 * ```cpp
 * auto sched = make_shared<Scheduler>(true);  // 引用计数 = 1
 * CoreWorker w(sched);  // 拷贝参数到成员，引用计数 = 2
 * // w.scheduler_ 和 sched 都指向同一对象
 *
 * auto sched2 = make_shared<Scheduler>(true);  // 引用计数 = 1
 * CoreWorker w2(std::move(sched2));  // 移动参数到成员，引用计数 = 1
 * // w2.scheduler_ 指向对象，sched2 = nullptr
 * ```
 *
 * 为什么这样设计？
 * - 调用方可以选择拷贝或移动
 * - 避免强制拷贝（如果参数是 const&）
 * - 避免强制移动（如果参数是 &&）
 * - 灵活性最大化
 */
CoreWorker::CoreWorker(
    std::shared_ptr<raylet::Scheduler> scheduler,
    std::shared_ptr<object_store::ObjectStore> object_store,
    int worker_id)
    : scheduler_(std::move(scheduler)),
      object_store_(std::move(object_store)),
      worker_id_(worker_id) {
}

ObjectRef CoreWorker::SubmitTask(const Task& task) {
    // 通过 -> 运算符调用 shared_ptr 指向的对象的方法
    // scheduler_ 是 shared_ptr<Scheduler>
    // scheduler_->SubmitTask(...) 等价于 (*scheduler_).SubmitTask(...)
    scheduler_->SubmitTask(task);

    // 返回任务的 return_ref
    // 调用方可以立即使用这个 ObjectRef，但 Get 时可能阻塞等待结果
    return task.return_ref;
}

std::shared_ptr<Task> CoreWorker::GetNextTask() {
    // 从调度器获取下一个任务
    // 如果队列为空，返回 nullptr
    return scheduler_->GetNextTask();
}

void CoreWorker::PutObject(const ObjectRef& object_ref,
                           const std::vector<uint8_t>& data) {
    // 使用指定的 ObjectRef 存储对象
    // ObjectRef 应该提前创建，避免竞态条件
    object_store_->Put(object_ref, data);
}

std::shared_ptr<Buffer> CoreWorker::GetObject(const ObjectRef& object_ref) {
    // 从对象存储获取对象
    // 返回 shared_ptr<Buffer>，自动管理生命周期
    return object_store_->Get(object_ref);
}

void CoreWorker::MarkWorkerBusy() {
    // 标记当前 Worker 为忙碌
    // worker_id_ 是成员变量，标识当前 Worker
    scheduler_->MarkWorkerBusy(worker_id_);
}

void CoreWorker::MarkWorkerIdle() {
    // 标记当前 Worker 为空闲
    scheduler_->MarkWorkerIdle(worker_id_);
}

}  // namespace core_worker
}  // namespace miniray

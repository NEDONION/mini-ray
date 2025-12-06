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
 * 初始化列表 + std::move 的最佳实践
 *
 * std::move 将参数转为右值，触发 shared_ptr 的移动构造
 * 比拷贝构造高效（不增加引用计数）
 */
CoreWorker::CoreWorker(
    std::shared_ptr<shared::SharedScheduler> scheduler,
    std::shared_ptr<shared::SharedObjectStore> object_store,
    int worker_id)
    : scheduler_(std::move(scheduler)),
      object_store_(std::move(object_store)),
      worker_id_(worker_id) {
}

ObjectRef CoreWorker::SubmitTask(const Task& task) {
    scheduler_->SubmitTask(task);
    return task.return_ref;
}

std::shared_ptr<Task> CoreWorker::GetNextTask() {
    return scheduler_->GetNextTask();
}

void CoreWorker::PutObject(const ObjectRef& object_ref,
                           const std::vector<uint8_t>& data) {
    object_store_->Put(object_ref, data);
}

std::shared_ptr<Buffer> CoreWorker::GetObject(const ObjectRef& object_ref) {
    return object_store_->Get(object_ref);
}

void CoreWorker::MarkWorkerBusy() {
    scheduler_->MarkWorkerBusy(worker_id_);
}

void CoreWorker::MarkWorkerIdle() {
    scheduler_->MarkWorkerIdle(worker_id_);
}

}  // namespace core_worker
}  // namespace miniray

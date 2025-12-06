/**
 * core_worker.h - CoreWorker 核心工作器
 *
 * ============================================================
 * C++ 设计模式和最佳实践
 * ============================================================
 *
 * 1. Facade（外观）模式
 *    封装多个子系统，提供统一的简化接口
 *    CoreWorker 封装了 Scheduler 和 ObjectStore
 *
 * 2. 依赖注入（Dependency Injection）
 *    通过构造函数传入依赖，而非内部创建
 *    好处：解耦、易于测试、易于替换实现
 *    最佳实践：大型系统中广泛使用
 *
 * 3. 智能指针的选择
 *    shared_ptr: 共享所有权（多个对象共用一个资源）
 *    unique_ptr: 独占所有权（一个对象独占资源）
 *    最佳实践：默认用 unique_ptr，需要共享时用 shared_ptr
 *
 * 4. inline 函数
 *    建议编译器内联展开，减少函数调用开销
 *    适用场景：简单的 getter/setter
 *    注意：只是建议，编译器可能不采纳
 *
 * 5. 禁用拷贝的场景
 *    管理资源的类（文件句柄、网络连接、锁等）
 *    单例类
 *    表示唯一实体的类（如 Worker）
 *    最佳实践：明确拷贝语义，有疑问就禁用
 */

#pragma once

#include <memory>
#include "miniray/common/buffer.h"
#include "miniray/shared/shared_scheduler.h"
#include "miniray/shared/shared_object_store.h"
#include "miniray/common/task.h"
#include "miniray/common/object_ref.h"

namespace miniray {
namespace core_worker {

class CoreWorker {
public:
    /**
     * 构造函数使用值传递智能指针
     *
     * 为什么传值而非 const&？
     * - 传值配合 std::move 更高效
     * - 明确表达所有权转移的语义
     * - 避免悬空引用的风险
     */
    CoreWorker(
        std::shared_ptr<shared::SharedScheduler> scheduler,
        std::shared_ptr<shared::SharedObjectStore> object_store,
        int worker_id);

    ~CoreWorker() = default;

    CoreWorker(const CoreWorker&) = delete;
    CoreWorker& operator=(const CoreWorker&) = delete;

    ObjectRef SubmitTask(const Task& task);
    std::shared_ptr<Task> GetNextTask();
    void PutObject(const ObjectRef& object_ref, const std::vector<uint8_t>& data);
    std::shared_ptr<Buffer> GetObject(const ObjectRef& object_ref);

    /**
     * inline 函数在头文件中定义
     *
     * 优点：编译器可以内联优化
     * 缺点：修改需要重新编译所有使用者
     * 最佳实践：只对简单函数使用 inline
     */
    inline int GetWorkerID() const {
        return worker_id_;
    }

    void MarkWorkerBusy();
    void MarkWorkerIdle();

private:
    std::shared_ptr<shared::SharedScheduler> scheduler_;
    std::shared_ptr<shared::SharedObjectStore> object_store_;
    int worker_id_;
};

}  // namespace core_worker
}  // namespace miniray

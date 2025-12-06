/**
 * scheduler.cpp - 调度器实现
 *
 * 本文件实现了 scheduler.h 中声明的 Scheduler 类
 */

#include "miniray/raylet/scheduler.h"

namespace miniray {
namespace raylet {

// ============================================================
// SchedulerLayout::SharedTask 实现
// ============================================================

void SchedulerLayout::SharedTask::FromTask(const Task& task) {
    // 拷贝元数据
    task_id = task.task_id;
    function_id = task.function_id;
    return_ref = task.return_ref;

    // 拷贝序列化的函数
    serialized_function_size = task.serialized_function.size();
    if (serialized_function_size > MAX_SERIALIZED_SIZE) {
        throw std::runtime_error("Serialized function too large");
    }
    std::memcpy(
        serialized_function,
        task.serialized_function.data(),
        serialized_function_size
    );

    // 拷贝序列化的参数
    serialized_args_size = task.serialized_args.size();
    if (serialized_args_size > MAX_SERIALIZED_SIZE) {
        throw std::runtime_error("Serialized args too large");
    }
    std::memcpy(
        serialized_args,
        task.serialized_args.data(),
        serialized_args_size
    );

    // 调试输出
    std::fprintf(stderr,
        "[C++ FromTask] 复制数据: func_size=%zu, args_size=%zu\n",
        serialized_function_size, serialized_args_size);
    std::fflush(stderr);
}

void SchedulerLayout::SharedTask::ToTask(Task& task) const {
    // 调试输出
    std::fprintf(stderr,
        "[C++ ToTask] 读取数据: func_size=%zu, args_size=%zu\n",
        serialized_function_size, serialized_args_size);
    std::fflush(stderr);

    // 拷贝元数据
    task.task_id = task_id;
    task.function_id = function_id;
    task.return_ref = return_ref;

    // 拷贝序列化的函数
    // vector::assign(begin, end) 替换 vector 内容
    task.serialized_function.assign(
        serialized_function,
        serialized_function + serialized_function_size
    );

    // 拷贝序列化的参数
    task.serialized_args.assign(
        serialized_args,
        serialized_args + serialized_args_size
    );
}

// ============================================================
// Scheduler 实现
// ============================================================

Scheduler::Scheduler(bool create)
    : shm_("/miniray_scheduler",
           SchedulerLayout::TotalSize(),
           create) {

    // 获取共享内存布局指针
    layout_ = static_cast<SchedulerLayout*>(shm_.GetAddress());

    if (create) {
        // 创建模式：初始化共享内存

        // placement new 构造 ProcessMutex
        new (&layout_->header.mutex) common::ProcessMutex();

        // 初始化队列状态
        layout_->header.task_count.store(0);
        layout_->header.head.store(0);
        layout_->header.tail.store(0);

        // 初始化所有 Worker 为未使用状态
        for (int i = 0; i < SchedulerLayout::MAX_WORKERS; i++) {
            layout_->workers[i].worker_id = -1;
            layout_->workers[i].is_idle.store(false);
        }
    }
}

void Scheduler::SubmitTask(const Task& task) {
    // 调试输出
    std::fprintf(stderr,
        "[C++ SubmitTask] 输入任务: func_size=%zu, args_size=%zu\n",
        task.serialized_function.size(), task.serialized_args.size());
    std::fflush(stderr);

    // RAII 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 检查队列是否已满
    int count = layout_->header.task_count.load();
    if (count >= SchedulerLayout::MAX_TASKS) {
        throw std::runtime_error("Task queue full");
    }

    // 获取 tail 位置
    int tail = layout_->header.tail.load();

    // 将 Task 拷贝到 SharedTask
    layout_->tasks[tail].FromTask(task);

    // 调试输出
    std::fprintf(stderr,
        "[C++ SubmitTask] 写入共享内存后: func_size=%zu, args_size=%zu\n",
        layout_->tasks[tail].serialized_function_size,
        layout_->tasks[tail].serialized_args_size);
    std::fflush(stderr);

    // 更新 tail（循环）
    layout_->header.tail.store((tail + 1) % SchedulerLayout::MAX_TASKS);

    // 增加任务计数
    layout_->header.task_count.fetch_add(1);
}

std::shared_ptr<Task> Scheduler::GetNextTask() {
    // RAII 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 检查队列是否为空
    int count = layout_->header.task_count.load();
    if (count == 0) {
        return nullptr;  // 队列为空
    }

    // 获取 head 位置
    int head = layout_->header.head.load();
    auto& slot = layout_->tasks[head];

    // 调试输出
    std::fprintf(stderr,
        "[C++ GetNextTask] 从共享内存读取: func_size=%zu, args_size=%zu\n",
        slot.serialized_function_size, slot.serialized_args_size);
    std::fflush(stderr);

    // 在堆上分配 Task 对象
    auto task = std::make_shared<Task>();

    // 将 SharedTask 拷贝到 Task
    slot.ToTask(*task);

    // 更新 head（循环）
    layout_->header.head.store((head + 1) % SchedulerLayout::MAX_TASKS);

    // 减少任务计数
    layout_->header.task_count.fetch_sub(1);

    return task;
}

void Scheduler::RegisterWorker(int worker_id) {
    // 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 查找空闲槽位
    for (int i = 0; i < SchedulerLayout::MAX_WORKERS; i++) {
        if (layout_->workers[i].worker_id == -1) {
            layout_->workers[i].worker_id = worker_id;
            layout_->workers[i].is_idle.store(true);
            return;
        }
    }

    // 槽位已满
    throw std::runtime_error("Too many workers");
}

void Scheduler::UnregisterWorker(int worker_id) {
    // 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 查找并注销
    for (int i = 0; i < SchedulerLayout::MAX_WORKERS; i++) {
        if (layout_->workers[i].worker_id == worker_id) {
            layout_->workers[i].worker_id = -1;
            layout_->workers[i].is_idle.store(false);
            return;
        }
    }
}

void Scheduler::MarkWorkerBusy(int worker_id) {
    // 不加锁（原子操作足够）
    for (int i = 0; i < SchedulerLayout::MAX_WORKERS; i++) {
        if (layout_->workers[i].worker_id == worker_id) {
            layout_->workers[i].is_idle.store(false);
            return;
        }
    }
}

void Scheduler::MarkWorkerIdle(int worker_id) {
    // 不加锁（原子操作足够）
    for (int i = 0; i < SchedulerLayout::MAX_WORKERS; i++) {
        if (layout_->workers[i].worker_id == worker_id) {
            layout_->workers[i].is_idle.store(true);
            return;
        }
    }
}

size_t Scheduler::GetPendingTaskCount() const {
    // 原子读取
    return layout_->header.task_count.load();
}

size_t Scheduler::GetIdleWorkerCount() const {
    // 不加锁（非关键路径）
    int count = 0;
    for (int i = 0; i < SchedulerLayout::MAX_WORKERS; i++) {
        if (layout_->workers[i].worker_id != -1 &&
            layout_->workers[i].is_idle.load()) {
            count++;
        }
    }
    return count;
}

bool Scheduler::HasIdleWorker() const {
    return GetIdleWorkerCount() > 0;
}

void Scheduler::Cleanup() {
    // 删除共享内存对象
    common::SharedMemory::Unlink("/miniray_scheduler");
}

}  // namespace raylet
}  // namespace miniray

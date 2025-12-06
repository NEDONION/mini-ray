#pragma once

#include "miniray/shared/shared_memory.h"
#include "miniray/common/task.h"
#include <atomic>
#include <memory>
#include <iostream>
#include <cstdio>
#include <cstring>
#include <stdexcept>

namespace miniray {
namespace shared {

/**
 * @brief 共享内存布局 - Scheduler 部分
 */
struct SharedSchedulerLayout {
    // 控制信息
    struct Header {
        ProcessMutex mutex;
        std::atomic<int> task_count;      // 当前任务数
        std::atomic<int> head;            // 队列头（读取位置）
        std::atomic<int> tail;            // 队列尾（写入位置）
        char padding[64];
    } header;

    // 任务队列（循环队列）
    static constexpr int MAX_TASKS = 100;
    static constexpr int MAX_SERIALIZED_SIZE = 64 * 1024;  // 64 KB per field

    struct SharedTask {
        TaskID task_id;
        FunctionID function_id;
        ObjectRef return_ref;

        size_t serialized_function_size;
        uint8_t serialized_function[MAX_SERIALIZED_SIZE];

        size_t serialized_args_size;
        uint8_t serialized_args[MAX_SERIALIZED_SIZE];

        SharedTask() : serialized_function_size(0), serialized_args_size(0) {}

        // 从 Task 转换（写入共享内存槽位）
        void FromTask(const Task& task) {
            task_id = task.task_id;
            function_id = task.function_id;
            return_ref = task.return_ref;

            serialized_function_size = task.serialized_function.size();
            if (serialized_function_size > MAX_SERIALIZED_SIZE) {
                throw std::runtime_error("Serialized function too large");
            }
            std::memcpy(
                serialized_function,
                task.serialized_function.data(),
                serialized_function_size
            );

            serialized_args_size = task.serialized_args.size();
            if (serialized_args_size > MAX_SERIALIZED_SIZE) {
                throw std::runtime_error("Serialized args too large");
            }
            std::memcpy(
                serialized_args,
                task.serialized_args.data(),
                serialized_args_size
            );

            std::fprintf(stderr,
                "[C++ FromTask] 复制数据: func_size=%zu, args_size=%zu\n",
                serialized_function_size, serialized_args_size);
            std::fflush(stderr);
        }

        // 从共享内存槽位读回到 Task（深拷贝到 vector）
        void ToTask(Task& task) const {
            std::fprintf(stderr,
                "[C++ ToTask] 读取数据: func_size=%zu, args_size=%zu\n",
                serialized_function_size, serialized_args_size);
            std::fflush(stderr);

            task.task_id = task_id;
            task.function_id = function_id;
            task.return_ref = return_ref;

            task.serialized_function.assign(
                serialized_function,
                serialized_function + serialized_function_size
            );

            task.serialized_args.assign(
                serialized_args,
                serialized_args + serialized_args_size
            );
        }
    };

    SharedTask tasks[MAX_TASKS];

    // Worker 状态
    static constexpr int MAX_WORKERS = 16;
    struct WorkerInfo {
        int worker_id;
        std::atomic<bool> is_idle;
        char padding[56];  // 缓存行对齐
    } workers[MAX_WORKERS];

    static constexpr size_t TotalSize() {
        return sizeof(SharedSchedulerLayout);
    }
};

/**
 * @brief 共享内存调度器
 */
class SharedScheduler {
public:
    explicit SharedScheduler(bool create = true)
        : shm_("/miniray_scheduler",
               SharedSchedulerLayout::TotalSize(),
               create) {

        layout_ = static_cast<SharedSchedulerLayout*>(shm_.GetAddress());

        if (create) {
            new (&layout_->header.mutex) ProcessMutex();
            layout_->header.task_count.store(0);
            layout_->header.head.store(0);
            layout_->header.tail.store(0);

            // 初始化 worker 状态
            for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
                layout_->workers[i].worker_id = -1;
                layout_->workers[i].is_idle.store(false);
            }
        }
    }

    ~SharedScheduler() = default;

    /**
     * @brief 提交任务
     */
    void SubmitTask(const Task& task) {
        std::fprintf(stderr,
            "[C++ SubmitTask] 输入任务: func_size=%zu, args_size=%zu\n",
            task.serialized_function.size(), task.serialized_args.size());
        std::fflush(stderr);

        LockGuard lock(layout_->header.mutex);

        int count = layout_->header.task_count.load();
        if (count >= SharedSchedulerLayout::MAX_TASKS) {
            throw std::runtime_error("Task queue full");
        }

        int tail = layout_->header.tail.load();
        layout_->tasks[tail].FromTask(task);

        std::fprintf(stderr,
            "[C++ SubmitTask] 写入共享内存后: func_size=%zu, args_size=%zu\n",
            layout_->tasks[tail].serialized_function_size,
            layout_->tasks[tail].serialized_args_size);
        std::fflush(stderr);

        layout_->header.tail.store((tail + 1) % SharedSchedulerLayout::MAX_TASKS);
        layout_->header.task_count.fetch_add(1);
    }

    /**
     * @brief 获取下一个任务（堆上构造 Task，再用 shared_ptr 返回）
     */
    std::shared_ptr<Task> GetNextTask() {
        LockGuard lock(layout_->header.mutex);

        int count = layout_->header.task_count.load();
        if (count == 0) {
            return nullptr;  // 队列为空
        }

        int head = layout_->header.head.load();
        auto& slot = layout_->tasks[head];

        std::fprintf(stderr,
            "[C++ GetNextTask] 从共享内存读取: func_size=%zu, args_size=%zu\n",
            slot.serialized_function_size, slot.serialized_args_size);
        std::fflush(stderr);

        auto task = std::make_shared<Task>();  // ✅ 在堆上分配
        slot.ToTask(*task);                    // ✅ 深拷贝到 Task 的 vector 里

        layout_->header.head.store((head + 1) % SharedSchedulerLayout::MAX_TASKS);
        layout_->header.task_count.fetch_sub(1);

        return task;
    }

    // 下面 worker 相关逻辑保持原样
    void RegisterWorker(int worker_id) {
        LockGuard lock(layout_->header.mutex);

        for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
            if (layout_->workers[i].worker_id == -1) {
                layout_->workers[i].worker_id = worker_id;
                layout_->workers[i].is_idle.store(true);
                return;
            }
        }
        throw std::runtime_error("Too many workers");
    }

    void UnregisterWorker(int worker_id) {
        LockGuard lock(layout_->header.mutex);

        for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
            if (layout_->workers[i].worker_id == worker_id) {
                layout_->workers[i].worker_id = -1;
                layout_->workers[i].is_idle.store(false);
                return;
            }
        }
    }

    void MarkWorkerBusy(int worker_id) {
        for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
            if (layout_->workers[i].worker_id == worker_id) {
                layout_->workers[i].is_idle.store(false);
                return;
            }
        }
    }

    void MarkWorkerIdle(int worker_id) {
        for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
            if (layout_->workers[i].worker_id == worker_id) {
                layout_->workers[i].is_idle.store(true);
                return;
            }
        }
    }

    size_t GetPendingTaskCount() const {
        return layout_->header.task_count.load();
    }

    size_t GetIdleWorkerCount() const {
        int count = 0;
        for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
            if (layout_->workers[i].worker_id != -1 &&
                layout_->workers[i].is_idle.load()) {
                count++;
            }
        }
        return count;
    }

    bool HasIdleWorker() const {
        return GetIdleWorkerCount() > 0;
    }

    static void Cleanup() {
        SharedMemory::Unlink("/miniray_scheduler");
    }

private:
    SharedMemory shm_;
    SharedSchedulerLayout* layout_;
};

} // namespace shared
} // namespace miniray

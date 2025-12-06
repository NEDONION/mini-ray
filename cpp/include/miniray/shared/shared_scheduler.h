#pragma once

#include "miniray/shared/shared_memory.h"
#include "miniray/common/task.h"
#include <atomic>
#include <memory>
#include <iostream>
#include <cstdio>

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

        // 使用固定大小数组而不是 vector（适合共享内存）
        size_t serialized_function_size;
        uint8_t serialized_function[MAX_SERIALIZED_SIZE];

        size_t serialized_args_size;
        uint8_t serialized_args[MAX_SERIALIZED_SIZE];

        SharedTask() : serialized_function_size(0), serialized_args_size(0) {}

        // 从 Task 转换
        void FromTask(const Task& task) {
            task_id = task.task_id;
            function_id = task.function_id;
            return_ref = task.return_ref;

            serialized_function_size = task.serialized_function.size();
            if (serialized_function_size > MAX_SERIALIZED_SIZE) {
                throw std::runtime_error("Serialized function too large");
            }
            std::memcpy(serialized_function, task.serialized_function.data(),
                       serialized_function_size);

            serialized_args_size = task.serialized_args.size();
            if (serialized_args_size > MAX_SERIALIZED_SIZE) {
                throw std::runtime_error("Serialized args too large");
            }
            std::memcpy(serialized_args, task.serialized_args.data(),
                       serialized_args_size);

            fprintf(stderr, "[C++ FromTask] 复制数据: func_size=%zu, args_size=%zu\n",
                    serialized_function_size, serialized_args_size);
            fflush(stderr);
        }

        // 转换为 Task
        Task ToTask() const {
            fprintf(stderr, "[C++ ToTask] 读取数据: func_size=%zu, args_size=%zu\n",
                    serialized_function_size, serialized_args_size);
            fflush(stderr);

            Task task;
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

            return task;
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
        fprintf(stderr, "[C++ SubmitTask] 输入任务: func_size=%zu, args_size=%zu\n",
                task.serialized_function.size(), task.serialized_args.size());
        fflush(stderr);

        LockGuard lock(layout_->header.mutex);

        int count = layout_->header.task_count.load();
        if (count >= SharedSchedulerLayout::MAX_TASKS) {
            throw std::runtime_error("Task queue full");
        }

        int tail = layout_->header.tail.load();
        layout_->tasks[tail].FromTask(task);

        fprintf(stderr, "[C++ SubmitTask] 写入共享内存后: func_size=%zu, args_size=%zu\n",
                layout_->tasks[tail].serialized_function_size, layout_->tasks[tail].serialized_args_size);
        fflush(stderr);

        // 循环队列
        layout_->header.tail.store((tail + 1) % SharedSchedulerLayout::MAX_TASKS);
        layout_->header.task_count.fetch_add(1);
    }

    /**
     * @brief 获取下一个任务
     */
    std::shared_ptr<Task> GetNextTask() {
        LockGuard lock(layout_->header.mutex);

        int count = layout_->header.task_count.load();
        if (count == 0) {
            return nullptr;  // 队列为空
        }

        int head = layout_->header.head.load();
        fprintf(stderr, "[C++ GetNextTask] 从共享内存读取: func_size=%zu, args_size=%zu\n",
                layout_->tasks[head].serialized_function_size, layout_->tasks[head].serialized_args_size);
        fflush(stderr);

        Task task = layout_->tasks[head].ToTask();

        // 循环队列
        layout_->header.head.store((head + 1) % SharedSchedulerLayout::MAX_TASKS);
        layout_->header.task_count.fetch_sub(1);

        return std::make_shared<Task>(task);
    }

    /**
     * @brief 注册 Worker
     */
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

    /**
     * @brief 注销 Worker
     */
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

    /**
     * @brief 标记 Worker 为忙碌
     */
    void MarkWorkerBusy(int worker_id) {
        for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
            if (layout_->workers[i].worker_id == worker_id) {
                layout_->workers[i].is_idle.store(false);
                return;
            }
        }
    }

    /**
     * @brief 标记 Worker 为空闲
     */
    void MarkWorkerIdle(int worker_id) {
        for (int i = 0; i < SharedSchedulerLayout::MAX_WORKERS; i++) {
            if (layout_->workers[i].worker_id == worker_id) {
                layout_->workers[i].is_idle.store(true);
                return;
            }
        }
    }

    /**
     * @brief 获取待处理任务数
     */
    size_t GetPendingTaskCount() const {
        return layout_->header.task_count.load();
    }

    /**
     * @brief 获取空闲 Worker 数量
     */
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

    /**
     * @brief 是否有空闲 Worker
     */
    bool HasIdleWorker() const {
        return GetIdleWorkerCount() > 0;
    }

    /**
     * @brief 清理共享内存
     */
    static void Cleanup() {
        SharedMemory::Unlink("/miniray_scheduler");
    }

private:
    SharedMemory shm_;
    SharedSchedulerLayout* layout_;
};

} // namespace shared
} // namespace miniray

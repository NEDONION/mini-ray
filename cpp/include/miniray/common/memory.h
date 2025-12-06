/**
 * memory.h - 共享内存管理基础设施
 *
 * ============================================================
 * 设计思想和架构
 * ============================================================
 *
 * 共享内存是进程间通信（IPC）的核心机制之一，本模块提供：
 * 1. SharedMemory: POSIX 共享内存的 RAII 封装
 * 2. ProcessMutex: 进程间互斥锁
 * 3. LockGuard: RAII 风格的锁管理
 *
 * ============================================================
 * POSIX 共享内存机制
 * ============================================================
 *
 * POSIX 提供了两种主要的共享内存方式：
 * 1. System V 共享内存 (shmget/shmat)
 *    - 较老的 API，使用整数 key
 *    - 生命周期独立于进程
 *
 * 2. POSIX 共享内存 (shm_open/mmap) ⬅ 本实现采用
 *    - 现代 API，使用路径名（如 "/miniray_shm"）
 *    - 更简洁、更符合 Unix 哲学
 *    - 自动内存映射，易于使用
 *
 * ============================================================
 * 内存映射 (mmap) 原理
 * ============================================================
 *
 * mmap 将文件或共享内存对象映射到进程的虚拟地址空间：
 * - MAP_SHARED: 多个进程共享同一物理内存
 * - 写入操作对所有进程可见
 * - 内核负责同步和缓存一致性
 *
 * ============================================================
 * 进程间同步机制
 * ============================================================
 *
 * pthread_mutex 配置为 PTHREAD_PROCESS_SHARED：
 * - 必须放在共享内存中
 * - 所有进程看到相同的锁状态
 * - 底层通过 futex 系统调用实现（Linux）
 *
 * ============================================================
 * RAII 模式的优势
 * ============================================================
 *
 * Resource Acquisition Is Initialization:
 * - 构造函数获取资源
 * - 析构函数释放资源
 * - 异常安全：即使抛出异常也会释放资源
 * - 无需手动管理，避免泄漏
 *
 * ============================================================
 * C++ 最佳实践
 * ============================================================
 *
 * 1. 显式删除拷贝构造/赋值
 *    - 资源管理类通常不应被拷贝
 *    - 使用 = delete 明确禁止
 *    - 如需转移所有权，实现移动语义
 *
 * 2. const 成员函数
 *    - 不修改对象状态的方法标记为 const
 *    - 编译器强制检查
 *    - 允许 const 对象调用
 *
 * 3. 构造函数参数
 *    - const std::string&: 避免拷贝大对象
 *    - 基本类型（int, bool）直接传值
 */

#pragma once

#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>
#include <atomic>
#include <cstring>
#include <stdexcept>
#include <string>

namespace miniray {
namespace common {

/**
 * @brief POSIX 共享内存的 RAII 封装
 *
 * 典型用法：
 * ```cpp
 * // 进程 A（创建者）
 * SharedMemory shm("/my_shm", 4096, true);
 * int* data = static_cast<int*>(shm.GetAddress());
 * *data = 42;
 *
 * // 进程 B（使用者）
 * SharedMemory shm("/my_shm", 4096, false);
 * int* data = static_cast<int*>(shm.GetAddress());
 * std::cout << *data;  // 输出 42
 * ```
 *
 * 线程安全性：
 * - SharedMemory 对象本身非线程安全
 * - 共享内存内容的访问需要自行同步（使用 ProcessMutex）
 */
class SharedMemory {
public:
    /**
     * @brief 创建或打开 POSIX 共享内存
     *
     * @param name 共享内存名称，必须以 '/' 开头（如 "/miniray_shm"）
     * @param size 内存大小（字节），创建时必须指定
     * @param create true=创建新共享内存，false=打开已存在的
     *
     * 实现细节：
     * 1. create=true 时先 shm_unlink 删除旧的（幂等性）
     * 2. shm_open 创建/打开共享内存对象（类似文件描述符）
     * 3. ftruncate 设置大小（仅 create=true）
     * 4. mmap 映射到进程地址空间
     * 5. create=true 时用 memset 清零
     *
     * 异常：如果操作失败，抛出 std::runtime_error
     */
    SharedMemory(const std::string& name, size_t size, bool create = true);

    /**
     * @brief 析构函数，自动释放资源
     *
     * RAII 保证：
     * - munmap 解除内存映射
     * - close 关闭文件描述符
     * - 即使构造中途失败，也会正确清理
     *
     * 注意：不会调用 shm_unlink，共享内存对象仍然存在
     *       需要主进程显式调用 SharedMemory::Unlink()
     */
    ~SharedMemory();

    // 禁止拷贝（资源管理类的最佳实践）
    SharedMemory(const SharedMemory&) = delete;
    SharedMemory& operator=(const SharedMemory&) = delete;

    /**
     * @brief 获取共享内存的起始地址
     *
     * 返回 void* 是因为：
     * - 共享内存可以存储任意类型
     * - 调用者负责转换为正确的类型
     * - 类似 malloc 的设计
     *
     * 示例：
     * ```cpp
     * auto* layout = static_cast<MyStruct*>(shm.GetAddress());
     * layout->field = value;
     * ```
     */
    void* GetAddress() const { return addr_; }

    /**
     * @brief 获取共享内存大小
     */
    size_t GetSize() const { return size_; }

    /**
     * @brief 删除共享内存对象
     *
     * 静态方法，无需 SharedMemory 实例即可调用
     * 通常在主进程退出时调用
     *
     * 注意：
     * - 即使有进程仍在使用，调用也会成功
     * - 已映射的内存仍然有效，但不能再被新进程打开
     * - 类似于 unlink 文件，最后一个引用消失后才真正删除
     */
    static void Unlink(const std::string& name);

private:
    std::string name_;  ///< 共享内存名称（如 "/miniray_shm"）
    size_t size_;       ///< 内存大小（字节）
    void* addr_;        ///< 映射后的虚拟地址
    int fd_;            ///< shm_open 返回的文件描述符
};

/**
 * @brief 进程间互斥锁
 *
 * 实现原理：
 * 1. pthread_mutex_t 配置为 PTHREAD_PROCESS_SHARED
 * 2. 必须放在共享内存中，让所有进程看到同一个锁
 * 3. 底层通过操作系统的 futex（快速用户空间互斥锁）实现
 *
 * 典型用法：
 * ```cpp
 * struct SharedData {
 *     ProcessMutex mutex;  // 必须在共享内存中！
 *     int counter;
 * };
 *
 * SharedMemory shm(...);
 * auto* data = static_cast<SharedData*>(shm.GetAddress());
 *
 * // 进程 A
 * {
 *     LockGuard lock(data->mutex);
 *     data->counter++;
 * }
 *
 * // 进程 B
 * {
 *     LockGuard lock(data->mutex);
 *     data->counter++;
 * }
 * ```
 *
 * 注意事项：
 * - ProcessMutex 对象本身必须在共享内存中
 * - 不能拷贝或移动（指针/引用传递）
 * - 未解锁就退出会导致死锁
 */
class ProcessMutex {
public:
    /**
     * @brief 构造函数，初始化进程共享锁
     *
     * 步骤：
     * 1. pthread_mutexattr_init 创建属性对象
     * 2. pthread_mutexattr_setpshared 设置为 PTHREAD_PROCESS_SHARED
     * 3. pthread_mutex_init 初始化锁
     * 4. pthread_mutexattr_destroy 销毁属性对象
     *
     * PTHREAD_PROCESS_SHARED vs PTHREAD_PROCESS_PRIVATE：
     * - SHARED: 可跨进程使用（必须在共享内存中）
     * - PRIVATE: 仅当前进程可用（默认值，性能更好）
     */
    ProcessMutex();

    /**
     * @brief 析构函数，销毁锁
     *
     * 调用 pthread_mutex_destroy 释放系统资源
     *
     * 注意：
     * - 销毁已加锁的互斥锁是未定义行为
     * - 务必确保所有线程/进程都已解锁
     */
    ~ProcessMutex();

    /**
     * @brief 加锁
     *
     * 阻塞直到获得锁
     * 如果已持有锁，再次加锁会死锁（非递归锁）
     */
    void lock();

    /**
     * @brief 解锁
     *
     * 只能由持有锁的线程/进程调用
     * 否则是未定义行为
     */
    void unlock();

    /**
     * @brief 获取底层 pthread_mutex_t 指针
     *
     * 用于高级用法，如条件变量
     */
    pthread_mutex_t* native_handle();

private:
    pthread_mutex_t mutex_;  ///< 底层 POSIX 互斥锁
};

/**
 * @brief RAII 风格的锁守卫
 *
 * 自动管理锁的生命周期：
 * - 构造时加锁
 * - 析构时解锁
 * - 异常安全
 *
 * 典型用法：
 * ```cpp
 * void SafeIncrement(ProcessMutex& mutex, int& counter) {
 *     LockGuard lock(mutex);  // 自动加锁
 *     counter++;
 *     // 可能抛出异常
 *     if (counter > 100) throw std::runtime_error("overflow");
 * }  // lock 析构，自动解锁（即使抛出异常）
 * ```
 *
 * 对比手动加锁：
 * ```cpp
 * // ❌ 不安全：异常导致不解锁
 * mutex.lock();
 * DoSomething();  // 可能抛异常
 * mutex.unlock();  // 永远不会执行
 *
 * // ✅ 安全：RAII 保证解锁
 * {
 *     LockGuard lock(mutex);
 *     DoSomething();
 * }  // 自动解锁
 * ```
 */
class LockGuard {
public:
    /**
     * @brief 构造时加锁
     *
     * explicit 关键字防止隐式转换：
     * ```cpp
     * ProcessMutex mutex;
     * LockGuard lock = mutex;  // ❌ 编译错误（如果没有 explicit）
     * LockGuard lock(mutex);   // ✅ 正确
     * ```
     */
    explicit LockGuard(ProcessMutex& mutex);

    /**
     * @brief 析构时解锁
     *
     * 标记为 noexcept（隐式）：
     * - 析构函数不应抛出异常（C++ 最佳实践）
     * - 如果析构中抛异常，程序会调用 std::terminate
     */
    ~LockGuard();

    // 禁止拷贝和移动（锁守卫不应被转移）
    LockGuard(const LockGuard&) = delete;
    LockGuard& operator=(const LockGuard&) = delete;
    LockGuard(LockGuard&&) = delete;
    LockGuard& operator=(LockGuard&&) = delete;

private:
    ProcessMutex& mutex_;  ///< 持有的互斥锁引用
};

}  // namespace common
}  // namespace miniray

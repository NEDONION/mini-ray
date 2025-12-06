/**
 * memory.cpp - 共享内存实现
 *
 * 本文件实现了 memory.h 中声明的类
 */

#include "miniray/common/memory.h"

namespace miniray {
namespace common {

// ============================================================
// SharedMemory 实现
// ============================================================

SharedMemory::SharedMemory(const std::string& name, size_t size, bool create)
    : name_(name), size_(size), addr_(nullptr), fd_(-1) {

    // 如果是创建模式，先删除可能存在的旧共享内存（幂等性）
    if (create) {
        shm_unlink(name_.c_str());  // 忽略错误
    }

    // 设置打开标志
    int flags = create ? (O_CREAT | O_RDWR) : O_RDWR;
    mode_t mode = 0666;  // rw-rw-rw-

    // 打开共享内存对象
    // shm_open 返回文件描述符，类似 open() 但操作共享内存
    fd_ = shm_open(name_.c_str(), flags, mode);
    if (fd_ == -1) {
        throw std::runtime_error("Failed to open shared memory: " + name_);
    }

    // 如果是创建模式，设置大小
    // ftruncate 调整文件/共享内存大小
    if (create) {
        if (ftruncate(fd_, size_) == -1) {
            close(fd_);
            throw std::runtime_error("Failed to set shared memory size");
        }
    }

    // 映射到进程地址空间
    // mmap 参数说明：
    // - nullptr: 让内核选择映射地址
    // - size_: 映射大小
    // - PROT_READ | PROT_WRITE: 可读可写
    // - MAP_SHARED: 共享映射（写入对其他进程可见）
    // - fd_: 共享内存文件描述符
    // - 0: 从偏移 0 开始映射
    addr_ = mmap(nullptr, size_, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
    if (addr_ == MAP_FAILED) {
        close(fd_);
        throw std::runtime_error("Failed to mmap shared memory");
    }

    // 如果是创建模式，初始化为零
    // 确保共享内存内容可预测
    if (create) {
        std::memset(addr_, 0, size_);
    }
}

SharedMemory::~SharedMemory() {
    // RAII: 析构时自动释放资源
    if (addr_ != nullptr && addr_ != MAP_FAILED) {
        munmap(addr_, size_);
    }
    if (fd_ != -1) {
        close(fd_);
    }
    // 注意：不调用 shm_unlink，由主进程显式控制
}

void SharedMemory::Unlink(const std::string& name) {
    // 删除共享内存对象
    // 类似 unlink 文件，最后一个引用消失后才真正删除
    shm_unlink(name.c_str());
}

// ============================================================
// ProcessMutex 实现
// ============================================================

ProcessMutex::ProcessMutex() {
    // 创建并初始化互斥锁属性
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);

    // 设置为进程共享（关键！）
    // 默认是 PTHREAD_PROCESS_PRIVATE（仅进程内可用）
    pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);

    // 用属性初始化互斥锁
    pthread_mutex_init(&mutex_, &attr);

    // 销毁属性对象（已经应用到 mutex_ 了）
    pthread_mutexattr_destroy(&attr);
}

ProcessMutex::~ProcessMutex() {
    // 销毁互斥锁，释放系统资源
    pthread_mutex_destroy(&mutex_);
}

void ProcessMutex::lock() {
    // 阻塞直到获得锁
    pthread_mutex_lock(&mutex_);
}

void ProcessMutex::unlock() {
    // 释放锁
    pthread_mutex_unlock(&mutex_);
}

pthread_mutex_t* ProcessMutex::native_handle() {
    // 返回底层锁指针，用于高级用法
    return &mutex_;
}

// ============================================================
// LockGuard 实现
// ============================================================

LockGuard::LockGuard(ProcessMutex& mutex) : mutex_(mutex) {
    // 构造时加锁
    mutex_.lock();
}

LockGuard::~LockGuard() {
    // 析构时解锁
    // RAII 保证即使抛出异常也会解锁
    mutex_.unlock();
}

}  // namespace common
}  // namespace miniray

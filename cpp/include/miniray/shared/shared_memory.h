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
namespace shared {

/**
 * @brief 简化的共享内存管理
 *
 * 使用 POSIX 共享内存实现进程间数据共享
 * 不需要完全像 Ray 那么复杂，够用就行
 */
class SharedMemory {
public:
    /**
     * @brief 创建或打开共享内存
     *
     * @param name 共享内存名称（如 "/miniray_shm"）
     * @param size 大小（字节）
     * @param create 是否创建（true）还是打开（false）
     */
    SharedMemory(const std::string& name, size_t size, bool create = true)
        : name_(name), size_(size), addr_(nullptr), fd_(-1) {

        // 如果是创建模式，先删除可能存在的旧共享内存
        if (create) {
            shm_unlink(name_.c_str());  // 忽略错误
        }

        int flags = create ? (O_CREAT | O_RDWR) : O_RDWR;
        mode_t mode = 0666;

        // 打开共享内存
        fd_ = shm_open(name_.c_str(), flags, mode);
        if (fd_ == -1) {
            throw std::runtime_error("Failed to open shared memory: " + name_);
        }

        // 如果是创建模式，设置大小
        if (create) {
            if (ftruncate(fd_, size_) == -1) {
                close(fd_);
                throw std::runtime_error("Failed to set shared memory size");
            }
        }

        // 映射到进程地址空间
        addr_ = mmap(nullptr, size_, PROT_READ | PROT_WRITE, MAP_SHARED, fd_, 0);
        if (addr_ == MAP_FAILED) {
            close(fd_);
            throw std::runtime_error("Failed to mmap shared memory");
        }

        // 如果是创建模式，初始化为零
        if (create) {
            std::memset(addr_, 0, size_);
        }
    }

    ~SharedMemory() {
        if (addr_ != nullptr && addr_ != MAP_FAILED) {
            munmap(addr_, size_);
        }
        if (fd_ != -1) {
            close(fd_);
        }
    }

    // 禁止拷贝
    SharedMemory(const SharedMemory&) = delete;
    SharedMemory& operator=(const SharedMemory&) = delete;

    /**
     * @brief 获取共享内存地址
     */
    void* GetAddress() const { return addr_; }

    /**
     * @brief 获取大小
     */
    size_t GetSize() const { return size_; }

    /**
     * @brief 删除共享内存（只在主进程退出时调用）
     */
    static void Unlink(const std::string& name) {
        shm_unlink(name.c_str());
    }

private:
    std::string name_;
    size_t size_;
    void* addr_;
    int fd_;
};

/**
 * @brief 进程间互斥锁包装
 */
class ProcessMutex {
public:
    ProcessMutex() {
        pthread_mutexattr_t attr;
        pthread_mutexattr_init(&attr);
        pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
        pthread_mutex_init(&mutex_, &attr);
        pthread_mutexattr_destroy(&attr);
    }

    ~ProcessMutex() {
        pthread_mutex_destroy(&mutex_);
    }

    void lock() {
        pthread_mutex_lock(&mutex_);
    }

    void unlock() {
        pthread_mutex_unlock(&mutex_);
    }

    pthread_mutex_t* native_handle() {
        return &mutex_;
    }

private:
    pthread_mutex_t mutex_;
};

/**
 * @brief RAII 锁守卫
 */
class LockGuard {
public:
    explicit LockGuard(ProcessMutex& mutex) : mutex_(mutex) {
        mutex_.lock();
    }

    ~LockGuard() {
        mutex_.unlock();
    }

private:
    ProcessMutex& mutex_;
};

} // namespace shared
} // namespace miniray

# Mini-Ray 共享内存实现指南

## Ray 的 Plasma Object Store 架构

### 核心特性

1. **基于 Apache Arrow Plasma** (Ray 现在维护自己的 fork)
2. **零拷贝读取** - 同节点进程直接访问共享内存
3. **自动对象迁移** - 跨节点自动传输对象
4. **LRU 淘汰策略** - 内存不足时自动淘汰旧对象

### Plasma 工作原理

```
┌─────────────────────────────────────────────────────┐
│                   Node (机器)                        │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │        Plasma Store (共享内存区域)             │  │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐    │  │
│  │  │Object│  │Object│  │Object│  │Object│    │  │
│  │  │  1   │  │  2   │  │  3   │  │  4   │    │  │
│  │  └──────┘  └──────┘  └──────┘  └──────┘    │  │
│  └──────────────────────────────────────────────┘  │
│         ↑           ↑           ↑                   │
│         │           │           │                   │
│    ┌────┴───┐  ┌───┴────┐  ┌───┴────┐             │
│    │Worker 1│  │Worker 2│  │Worker 3│             │
│    └────────┘  └────────┘  └────────┘             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 技术实现

#### 1. POSIX 共享内存 (Linux/macOS)

```cpp
// 创建共享内存段
int fd = shm_open("/miniray_plasma", O_CREAT | O_RDWR, 0666);
ftruncate(fd, SHARED_MEMORY_SIZE);

// 映射到进程地址空间
void* addr = mmap(NULL, SHARED_MEMORY_SIZE,
                  PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
```

#### 2. Unix Domain Socket 通信

Plasma 使用 Unix socket 在客户端和存储进程间通信：

```
Client (Worker) → Unix Socket → Plasma Store Server
     ↓                              ↓
  请求分配对象                   在共享内存中分配
     ↓                              ↓
  获得内存地址 ← Unix Socket ←  返回内存地址
     ↓
  直接读写共享内存（零拷贝）
```

#### 3. 对象元数据管理

```cpp
struct ObjectMetadata {
    ObjectID id;           // 对象唯一标识
    size_t size;          // 对象大小
    size_t offset;        // 在共享内存中的偏移
    int ref_count;        // 引用计数
    time_t create_time;   // 创建时间（用于 LRU）
};

// 元数据存储在单独的 hash table
std::unordered_map<ObjectID, ObjectMetadata> metadata_table;
```

---

## Mini-Ray 简化实现方案

### 方案 A: POSIX 共享内存 + 自定义管理（推荐学习）

**架构：**

```cpp
// 1. 共享内存布局
struct SharedMemoryLayout {
    // 头部：控制信息
    struct Header {
        std::atomic<size_t> next_offset;  // 下一个可用位置
        std::atomic<int> object_count;    // 对象数量
        pthread_mutex_t mutex;            // 互斥锁（进程间）
    } header;

    // 元数据区：对象索引表
    struct MetadataRegion {
        static const int MAX_OBJECTS = 1000;
        ObjectMetadata objects[MAX_OBJECTS];
    } metadata;

    // 数据区：实际对象存储
    uint8_t data[OBJECT_DATA_SIZE];
};
```

**实现步骤：**

1. **创建共享内存段**

```cpp
class SharedMemoryObjectStore {
private:
    int shm_fd_;
    SharedMemoryLayout* layout_;
    size_t total_size_;

public:
    SharedMemoryObjectStore(const std::string& name, size_t size) {
        // 创建共享内存
        shm_fd_ = shm_open(name.c_str(), O_CREAT | O_RDWR, 0666);
        if (shm_fd_ == -1) {
            throw std::runtime_error("Failed to create shared memory");
        }

        // 设置大小
        if (ftruncate(shm_fd_, size) == -1) {
            throw std::runtime_error("Failed to set shared memory size");
        }

        // 映射到进程地址空间
        void* addr = mmap(NULL, size, PROT_READ | PROT_WRITE,
                         MAP_SHARED, shm_fd_, 0);
        if (addr == MAP_FAILED) {
            throw std::runtime_error("Failed to map shared memory");
        }

        layout_ = static_cast<SharedMemoryLayout*>(addr);
        total_size_ = size;

        // 初始化互斥锁为进程间共享
        pthread_mutexattr_t attr;
        pthread_mutexattr_init(&attr);
        pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
        pthread_mutex_init(&layout_->header.mutex, &attr);
        pthread_mutexattr_destroy(&attr);
    }

    ~SharedMemoryObjectStore() {
        pthread_mutex_destroy(&layout_->header.mutex);
        munmap(layout_, total_size_);
        close(shm_fd_);
        shm_unlink("/miniray_plasma");
    }
};
```

2. **Put 操作（零拷贝）**

```cpp
ObjectRef Put(const std::vector<uint8_t>& data) {
    pthread_mutex_lock(&layout_->header.mutex);

    // 分配空间
    size_t offset = layout_->header.next_offset.load();
    size_t size = data.size();

    if (offset + size > OBJECT_DATA_SIZE) {
        pthread_mutex_unlock(&layout_->header.mutex);
        throw std::runtime_error("Shared memory full");
    }

    // 写入数据（直接内存拷贝）
    std::memcpy(&layout_->data[offset], data.data(), size);

    // 更新元数据
    ObjectID id = ObjectID::FromRandom();
    int idx = layout_->header.object_count.fetch_add(1);
    layout_->metadata.objects[idx] = {
        .id = id,
        .size = size,
        .offset = offset,
        .ref_count = 0,
        .create_time = time(nullptr)
    };

    layout_->header.next_offset.store(offset + size);

    pthread_mutex_unlock(&layout_->header.mutex);

    return ObjectRef(id);
}
```

3. **Get 操作（零拷贝读取）**

```cpp
std::shared_ptr<Buffer> Get(const ObjectRef& ref) {
    pthread_mutex_lock(&layout_->header.mutex);

    // 查找元数据
    ObjectMetadata* meta = nullptr;
    int count = layout_->header.object_count.load();
    for (int i = 0; i < count; i++) {
        if (layout_->metadata.objects[i].id == ref.GetObjectID()) {
            meta = &layout_->metadata.objects[i];
            break;
        }
    }

    if (!meta) {
        pthread_mutex_unlock(&layout_->header.mutex);
        throw std::runtime_error("Object not found");
    }

    // 零拷贝：直接返回指向共享内存的指针
    uint8_t* data_ptr = &layout_->data[meta->offset];
    auto buffer = std::make_shared<Buffer>(data_ptr, meta->size);

    pthread_mutex_unlock(&layout_->header.mutex);

    return buffer;
}
```

### 方案 B: Boost.Interprocess（更简单）

```cpp
#include <boost/interprocess/managed_shared_memory.hpp>
#include <boost/interprocess/containers/map.hpp>
#include <boost/interprocess/containers/vector.hpp>

using namespace boost::interprocess;

class BoostSharedObjectStore {
private:
    managed_shared_memory segment_;

public:
    BoostSharedObjectStore()
        : segment_(open_or_create, "MiniRaySharedMemory", 65536) {}

    ObjectRef Put(const std::vector<uint8_t>& data) {
        // Boost 自动管理共享内存分配
        auto* vec = segment_.construct<vector<uint8_t>>(
            anonymous_instance
        )(data.begin(), data.end(), segment_.get_allocator<uint8_t>());

        ObjectID id = ObjectID::FromRandom();
        // 存储指针...
        return ObjectRef(id);
    }
};
```

---

## Scheduler 的共享内存实现

### 任务队列共享

```cpp
struct SharedScheduler {
    // 使用循环队列（无锁或带锁）
    struct TaskQueue {
        static const int MAX_TASKS = 100;
        Task tasks[MAX_TASKS];
        std::atomic<int> head;
        std::atomic<int> tail;
        pthread_mutex_t mutex;
    };

    TaskQueue task_queue;

    // Worker 状态
    struct WorkerState {
        int worker_id;
        std::atomic<bool> is_idle;
    };
    WorkerState workers[MAX_WORKERS];
};
```

---

## 完整实现检查清单

### Phase 1: 基础共享内存

- [ ] 创建 POSIX 共享内存段
- [ ] 实现进程间互斥锁
- [ ] 实现基本的 Put/Get 操作
- [ ] 测试多进程访问

### Phase 2: 对象管理

- [ ] 实现对象元数据表
- [ ] 实现对象查找（哈希表）
- [ ] 实现引用计数
- [ ] 实现对象删除

### Phase 3: 调度器共享

- [ ] 实现共享任务队列
- [ ] 实现 Worker 状态管理
- [ ] 测试任务提交和获取

### Phase 4: 优化

- [ ] 实现 LRU 淘汰策略
- [ ] 优化锁粒度（减少锁竞争）
- [ ] 实现对象池（减少分配开销）

---

## 调试技巧

### 1. 查看共享内存

```bash
# Linux
ls -lh /dev/shm/

# macOS
ls -lh /tmp/

# 删除遗留的共享内存
rm /dev/shm/miniray_*
```

### 2. 检查锁状态

```cpp
// 添加超时检测
struct timespec timeout;
clock_gettime(CLOCK_REALTIME, &timeout);
timeout.tv_sec += 5;  // 5 秒超时

if (pthread_mutex_timedlock(&mutex, &timeout) != 0) {
    std::cerr << "Lock timeout! Possible deadlock." << std::endl;
}
```

### 3. 内存布局可视化

```cpp
void DumpMemoryLayout() {
    std::cout << "=== Shared Memory Layout ===" << std::endl;
    std::cout << "Header offset: 0" << std::endl;
    std::cout << "Metadata offset: " << offsetof(SharedMemoryLayout, metadata) << std::endl;
    std::cout << "Data offset: " << offsetof(SharedMemoryLayout, data) << std::endl;
    std::cout << "Object count: " << layout_->header.object_count.load() << std::endl;
    std::cout << "Next offset: " << layout_->header.next_offset.load() << std::endl;
}
```

---

## 常见陷阱

### 1. ❌ Fork 后的锁状态

**问题**: Fork 后子进程继承了父进程的锁状态，可能导致死锁。

**解决**: 使用 `PTHREAD_PROCESS_SHARED` 属性：

```cpp
pthread_mutexattr_t attr;
pthread_mutexattr_init(&attr);
pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
pthread_mutex_init(&mutex, &attr);
```

### 2. ❌ 指针在不同进程中失效

**问题**: 共享内存在不同进程中映射地址可能不同。

**解决**: 使用偏移量而非绝对指针：

```cpp
// ❌ 错误
uint8_t* ptr = &shared_memory[offset];

// ✅ 正确
size_t offset = ...;  // 保存偏移量
uint8_t* ptr = &layout_->data[offset];  // 每次重新计算
```

### 3. ❌ 内存泄漏

**问题**: 共享内存在进程退出后不会自动清理。

**解决**: 使用 RAII 和 `shm_unlink`：

```cpp
~SharedMemoryObjectStore() {
    munmap(layout_, total_size_);
    close(shm_fd_);
    shm_unlink("/miniray_plasma");  // 清理
}
```

---

## 参考资料

### Ray/Plasma 相关
- [The Plasma In-Memory Object Store](https://ray-project.github.io/2017/08/08/plasma-in-memory-object-store.html)
- [Ray GitHub - Plasma Fork](https://github.com/ray-project/plasma)
- [Ray Memory Management](https://docs.ray.io/en/latest/ray-core/scheduling/memory-management.html)

### 技术文档
- [POSIX Shared Memory](https://man7.org/linux/man-pages/man7/shm_overview.7.html)
- [Boost.Interprocess](https://www.boost.org/doc/libs/release/doc/html/interprocess.html)
- [Apache Arrow Plasma (已弃用)](https://arrow.apache.org/blog/2017/08/08/plasma-in-memory-object-store/)

---

## 下一步

选择实现方案：

1. **快速原型** → 方案 B (Boost.Interprocess)
2. **深入学习** → 方案 A (POSIX 手动实现)
3. **生产级别** → 参考 Ray 的完整实现

我可以帮你实现任何一个方案！

/**
 * object_store.h - 共享内存对象存储
 *
 * ============================================================
 * 设计思想和架构
 * ============================================================
 *
 * ObjectStore 是 Mini-Ray 的核心组件之一，负责：
 * 1. 存储任务的输入参数和返回值
 * 2. 提供进程间的对象共享机制
 * 3. 管理对象的生命周期
 *
 * 类比 Ray 的设计：
 * - Ray 使用 Apache Arrow Plasma 作为对象存储
 * - Mini-Ray 简化版：固定大小槽位 + 共享内存
 *
 * ============================================================
 * 内存布局设计
 * ============================================================
 *
 * SharedObjectStoreLayout 描述共享内存的结构：
 *
 * +-------------------+
 * | Header            |  <-- 元数据（锁、计数器）
 * +-------------------+
 * | ObjectSlot[0]     |  <-- 对象槽位数组
 * | ObjectSlot[1]     |
 * | ...               |
 * | ObjectSlot[999]   |
 * +-------------------+
 *
 * 每个 ObjectSlot：
 * +-----------------+
 * | ObjectID        |  <-- 对象唯一标识
 * | occupied (bool) |  <-- 是否被占用
 * | size (size_t)   |  <-- 数据大小
 * | data[64KB]      |  <-- 实际数据
 * +-----------------+
 *
 * ============================================================
 * 并发控制策略
 * ============================================================
 *
 * 1. 粗粒度锁（当前实现）
 *    - 一个全局锁保护整个 ObjectStore
 *    - 优点：简单、不会死锁
 *    - 缺点：并发性能受限
 *
 * 2. 细粒度锁（生产系统）
 *    - 每个槽位一个锁
 *    - 优点：高并发
 *    - 缺点：复杂、可能死锁
 *
 * 3. 无锁数据结构（高性能系统）
 *    - 使用 CAS（Compare-And-Swap）操作
 *    - 优点：最高性能
 *    - 缺点：极其复杂、难以调试
 *
 * Mini-Ray 采用 #1（粗粒度锁）：适合教学和小规模使用
 *
 * ============================================================
 * 对象生命周期
 * ============================================================
 *
 * 1. Put 阶段：
 *    - 生成或接收 ObjectRef
 *    - 寻找空闲槽位
 *    - 拷贝数据到共享内存
 *    - 标记槽位为占用
 *
 * 2. Get 阶段：
 *    - 根据 ObjectRef 查找槽位
 *    - 拷贝数据到 Buffer
 *    - 返回给调用者
 *
 * 3. Delete 阶段：
 *    - 标记槽位为未占用
 *    - 数据仍在内存中，但可被覆盖
 *
 * 注意：Mini-Ray 不支持引用计数和自动垃圾回收（简化设计）
 *
 * ============================================================
 * 内存对齐和缓存行
 * ============================================================
 *
 * Header 中的 padding：
 * - 现代 CPU 缓存行通常是 64 字节
 * - padding 确保不同字段不在同一缓存行
 * - 避免"伪共享"（false sharing）
 *
 * 伪共享示例：
 * ```
 * struct Data {
 *     std::atomic<int> counter1;  // 线程 A 频繁修改
 *     std::atomic<int> counter2;  // 线程 B 频繁修改
 * };
 * ```
 * 如果 counter1 和 counter2 在同一缓存行：
 * - 线程 A 修改 counter1 → 使线程 B 的缓存失效
 * - 线程 B 修改 counter2 → 使线程 A 的缓存失效
 * - 性能严重下降
 *
 * 解决：padding 确保不同原子变量在不同缓存行
 *
 * ============================================================
 * C++ 特性运用
 * ============================================================
 *
 * 1. constexpr
 *    - 编译时常量表达式
 *    - 可用于数组大小等编译时计算
 *    - 比 #define 更类型安全
 *
 * 2. std::atomic<T>
 *    - 原子操作，保证多线程/进程安全
 *    - 无需额外加锁即可安全访问
 *    - 常用操作：load(), store(), fetch_add()
 *
 * 3. 显式构造函数
 *    - ObjectSlot() 是显式默认构造
 *    - 确保成员被正确初始化
 *
 * 4. std::memcpy
 *    - 高效的内存拷贝
 *    - 适用于 POD（Plain Old Data）类型
 *    - 比循环赋值快得多
 */

#pragma once

#include "miniray/common/memory.h"
#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include "miniray/common/buffer.h"

#include <atomic>
#include <vector>
#include <cstring>
#include <stdexcept>

namespace miniray {
namespace object_store {

/**
 * @brief 对象存储的共享内存布局
 *
 * 该结构体直接映射到共享内存，定义了内存中的数据组织方式
 *
 * 设计考量：
 * - 固定大小：简化内存管理，避免碎片
 * - 槽位数组：类似哈希表的开放寻址法
 * - 原子操作：occupied 用 atomic 保证并发安全
 */
struct ObjectStoreLayout {
    /**
     * @brief 头部元数据
     *
     * 包含全局状态和同步原语
     */
    struct Header {
        common::ProcessMutex mutex;        ///< 保护整个 ObjectStore 的锁
        std::atomic<int> object_count;     ///< 当前对象数量
        char padding[64];                  ///< 缓存行填充，避免伪共享
    } header;

    // 容量限制（constexpr = 编译时常量）
    static constexpr int MAX_OBJECTS = 1000;                ///< 最大对象数
    static constexpr int MAX_OBJECT_SIZE = 64 * 1024;       ///< 单个对象最大 64KB

    /**
     * @brief 对象槽位
     *
     * 每个槽位存储一个对象
     * 类似哈希表的 bucket，但使用线性搜索
     */
    struct ObjectSlot {
        ObjectID id;                        ///< 对象 ID（128 位）
        std::atomic<bool> occupied;         ///< 是否被占用（原子操作）
        size_t size;                        ///< 数据实际大小
        uint8_t data[MAX_OBJECT_SIZE];      ///< 数据缓冲区

        /**
         * @brief 默认构造函数
         *
         * 初始化槽位为空闲状态
         * occupied 使用 atomic 的默认构造（值为 false）
         */
        ObjectSlot() : occupied(false), size(0) {}
    } slots[MAX_OBJECTS];  ///< 槽位数组

    /**
     * @brief 计算总共需要的共享内存大小
     *
     * constexpr 表示可在编译时计算
     * 用于创建 SharedMemory 时指定大小
     */
    static constexpr size_t TotalSize() {
        return sizeof(ObjectStoreLayout);
    }
};

/**
 * @brief 共享内存对象存储
 *
 * 封装对象存储的所有操作，对外提供简洁的 API
 *
 * 线程安全性：
 * - 所有公有方法都是线程/进程安全的
 * - 内部使用 ProcessMutex 保护共享状态
 *
 * 使用示例：
 * ```cpp
 * // 进程 A（创建者）
 * ObjectStore store(true);
 * std::vector<uint8_t> data = {1, 2, 3};
 * ObjectRef ref = store.Put(data);
 *
 * // 进程 B（使用者）
 * ObjectStore store(false);
 * auto buffer = store.Get(ref);
 * ```
 */
class ObjectStore {
public:
    /**
     * @brief 构造函数
     *
     * @param create true=创建新的 ObjectStore，false=连接已存在的
     *
     * 实现细节：
     * 1. 创建/打开共享内存
     * 2. 获取 ObjectStoreLayout 指针
     * 3. 如果是创建模式，初始化所有字段
     *    - 使用 placement new 在共享内存中构造对象
     *    - 初始化 mutex、counter、所有 slots
     *
     * placement new 语法：
     * ```cpp
     * new (&existing_memory) Type(args...);
     * ```
     * 在已有内存上构造对象，不分配新内存
     */
    explicit ObjectStore(bool create = true);

    /**
     * @brief 析构函数
     *
     * 使用默认析构（shm_ 的 RAII 会自动清理）
     * 不需要手动 munmap 或 close
     */
    ~ObjectStore() = default;

    /**
     * @brief 存储对象（自动生成 ID）
     *
     * @param data 对象数据
     * @return 对象的引用（ObjectRef）
     *
     * 算法：
     * 1. 检查数据大小
     * 2. 加锁
     * 3. 线性搜索空闲槽位
     * 4. 生成随机 ObjectID
     * 5. 拷贝数据
     * 6. 标记槽位为占用
     * 7. 增加计数器
     * 8. 返回 ObjectRef
     *
     * 时间复杂度：O(n)，n 为槽位数
     * 空间复杂度：O(1)
     *
     * 异常：如果对象过大或 ObjectStore 已满，抛出 runtime_error
     */
    ObjectRef Put(const std::vector<uint8_t>& data);

    /**
     * @brief 存储对象（使用指定的 ObjectRef）
     *
     * @param ref 调用方提供的 ObjectRef（已包含 ObjectID）
     * @param data 对象数据
     * @return 相同的 ObjectRef
     *
     * 用途：
     * - 任务提交前创建返回值的 ObjectRef
     * - 确保 ObjectRef 在任务执行前就存在
     * - 避免循环依赖和竞态条件
     *
     * 实现与 Put(data) 类似，但使用调用方的 ID
     */
    ObjectRef Put(const ObjectRef& ref, const std::vector<uint8_t>& data);

    /**
     * @brief 获取对象
     *
     * @param ref 对象引用
     * @return 对象数据的 Buffer（shared_ptr）
     *
     * 算法：
     * 1. 加锁
     * 2. 线性搜索匹配的 ObjectID
     * 3. 拷贝数据到新的 Buffer
     * 4. 返回 Buffer
     *
     * 为什么返回 shared_ptr<Buffer>？
     * - Buffer 可能很大，避免拷贝
     * - shared_ptr 自动管理生命周期
     * - 可以安全地传递给其他组件
     *
     * 异常：如果对象不存在，抛出 runtime_error
     */
    std::shared_ptr<Buffer> Get(const ObjectRef& ref);

    /**
     * @brief 检查对象是否存在
     *
     * @param ref 对象引用
     * @return true=存在，false=不存在
     *
     * 注意：没有加锁（性能优化）
     * - 适用于 "hint" 式检查
     * - 不保证强一致性（可能出现 TOCTOU）
     *
     * TOCTOU (Time-of-Check to Time-of-Use)：
     * ```cpp
     * if (store.Contains(ref)) {
     *     // 另一个进程可能在这里删除了对象
     *     auto buf = store.Get(ref);  // 可能抛异常
     * }
     * ```
     */
    bool Contains(const ObjectRef& ref) const;

    /**
     * @brief 删除对象
     *
     * @param ref 对象引用
     *
     * 实现：
     * 1. 加锁
     * 2. 查找对象
     * 3. 标记槽位为未占用
     * 4. 减少计数器
     *
     * 注意：
     * - 数据仍在内存中，但会被后续 Put 覆盖
     * - 如果对象不存在，静默返回（幂等性）
     */
    void Delete(const ObjectRef& ref);

    /**
     * @brief 获取对象数量
     *
     * @return 当前存储的对象数
     *
     * 原子操作，不需要加锁
     */
    size_t Size() const;

    /**
     * @brief 清理共享内存
     *
     * 静态方法，删除共享内存对象
     * 通常在主进程退出时调用
     *
     * 用法：
     * ```cpp
     * ObjectStore::Cleanup();
     * ```
     */
    static void Cleanup();

private:
    common::SharedMemory shm_;           ///< 共享内存管理器
    ObjectStoreLayout* layout_;          ///< 指向共享内存布局的指针
};

}  // namespace object_store
}  // namespace miniray

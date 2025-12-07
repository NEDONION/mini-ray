/**
 * object_store.h - 共享内存对象存储（v2：变长对象版本）
 *
 * ============================================================
 * 设计思想和架构（新版本）
 * ============================================================
 *
 * 相比 v1（每个槽位内嵌 64KB data）：
 *
 * 1. 支持变长对象
 *    - 新增 data_region（一整块连续的共享内存）
 *    - 每个 ObjectSlot 只保存 offset + size
 *    - 只要 data_region 够大，一个对象可以是几百 KB、几 MB 都可以
 *
 * 2. 简化并发模型
 *    - 仍然使用单个全局 ProcessMutex 粗粒度加锁
 *    - Put / Get / Delete 全部在锁保护下执行
 *    - Contains() 仅作为 hint，无锁读 occupied + id
 *
 * 3. 更接近 Plasma 的思路
 *    - 元数据（slot + header）和数据区（data_region）分离
 *    - 后续可以在 data_region 上实现更复杂的分配策略（free list / compaction）
 *
 * ============================================================
 * 内存布局设计（新版本）
 * ============================================================
 *
 * ObjectStoreLayout 描述共享内存结构：
 *
 * +---------------------------+
 * | Header                    |
 * +---------------------------+
 * | ObjectSlot[MAX_OBJECTS]   |  元数据区
 * +---------------------------+
 * | data_region[DATA_SIZE]    |  实际对象数据
 * +---------------------------+
 *
 * 每个 ObjectSlot：
 * +-----------------+
 * | ObjectID        |
 * | occupied (bool) |
 * | offset (size_t) |  <-- 相对于 data_region 起始地址的偏移
 * | size   (size_t) |
 * +-----------------+
 *
 * Put 时：
 * - 在 data_region 上分配 size 字节（bump allocator）
 * - 记录 offset + size
 * - 拷贝数据
 *
 * Get 时：
 * - 根据 offset + size，从 data_region 中拷贝出来
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
 * @brief 对象存储的共享内存布局（变长对象版本）
 */
struct ObjectStoreLayout {
    /**
     * @brief 头部元数据
     */
    struct Header {
        common::ProcessMutex mutex;        ///< 保护整个 ObjectStore 的锁
        std::atomic<int> object_count;     ///< 当前对象数量
        std::atomic<size_t> data_offset;   ///< data_region 已使用偏移（bump allocator）
        char padding[64];                  ///< 缓存行填充，避免与后续数据伪共享
    } header;

    // 容量限制（constexpr = 编译时常量）
    static constexpr int    MAX_OBJECTS       = 1000;             ///< 最大对象数
    static constexpr size_t DATA_REGION_SIZE  = 64 * 1024 * 1024; ///< 数据区总大小：64MB（可按需调整）

    /**
     * @brief 对象槽位（只保存元数据 + data_region 的位置）
     */
    struct ObjectSlot {
        ObjectID id;                        ///< 对象 ID（128 位）
        std::atomic<bool> occupied;         ///< 是否被占用
        size_t offset;                      ///< 在 data_region 中的偏移
        size_t size;                        ///< 数据实际大小

        ObjectSlot()
            : occupied(false), offset(0), size(0) {}
    } slots[MAX_OBJECTS];                   ///< 槽位数组

    /**
     * @brief 数据区：实际存储对象字节内容
     *
     * 所有对象的数据都存放在这块连续的内存中：
     * - Put 时：从 header.data_offset 处分配一块 size 字节
     * - Get 时：根据 slot.offset + slot.size 拷贝出去
     *
     * v2 先采用最简单的「只增不减」策略：
     * - Delete 只标记 slot.occupied = false，data_region 不回收
     * - 用于教学和小规模实验足够
     * - 未来可以扩展 free list / compaction 机制
     */
    uint8_t data_region[DATA_REGION_SIZE];

    /**
     * @brief 计算总共需要的共享内存大小
     */
    static constexpr size_t TotalSize() {
        return sizeof(ObjectStoreLayout);
    }
};

/**
 * @brief 共享内存对象存储
 *
 * 对外 API 不变，但语义略有变化：
 * - Put / Get / Delete 针对变长对象
 * - 内部通过 offset + size 在 data_region 中寻址
 */
class ObjectStore {
public:
    explicit ObjectStore(bool create = true);
    ~ObjectStore() = default;

    /**
     * @brief 存储对象（自动生成 ID）
     *
     * 如果 data_region 剩余空间不足，会抛出 std::runtime_error。
     */
    ObjectRef Put(const std::vector<uint8_t>& data);

    /**
     * @brief 存储对象（使用调用方提供的 ObjectRef）
     */
    ObjectRef Put(const ObjectRef& ref, const std::vector<uint8_t>& data);

    /**
     * @brief 获取对象
     *
     * 注意：仍然会把数据拷贝到新的 Buffer 中返回，
     * 如果你以后想要「零拷贝」，可以：
     * - 返回一个指向 data_region 的只读视图（带 ref count）
     * - 或者在 Python 层用 mmap + numpy.frombuffer() 直接视图访问
     */
    std::shared_ptr<Buffer> Get(const ObjectRef& ref);

    /**
     * @brief 检查对象是否存在（仅作 hint）
     */
    bool Contains(const ObjectRef& ref) const;

    /**
     * @brief 删除对象（幂等）
     *
     * 目前 Delete 只会：
     * - 标记 slot.occupied = false
     * - object_count--
     *
     * data_region 中的数据不会立刻回收。
     * 如果要做真正的空间回收，可以在未来加入：
     * - free list
     * - compaction
     */
    void Delete(const ObjectRef& ref);

    /**
     * @brief 当前对象数量
     */
    size_t Size() const;

    /**
     * @brief 清理共享内存（销毁底层 SharedMemory 对象）
     */
    static void Cleanup();

private:
    common::SharedMemory shm_;           ///< 共享内存管理器
    ObjectStoreLayout* layout_;          ///< 指向共享内存布局的指针
};

}  // namespace object_store
}  // namespace miniray

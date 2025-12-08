/**
 * object_store.h - 共享内存对象存储（v3：支持 Free List 内存回收）
 *
 * 优化目标：解决内存泄漏问题，提升容量，支持长时间分布式训练。
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
#include <cmath>

namespace miniray {
namespace object_store {

// 前向声明 ObjectStore 的核心布局
struct ObjectStoreLayout;

/**
 * @brief 内存管理的核心结构：空闲块（用于 Free List）
 * * 这个结构体将被放置在 data_region 内部，占用一块空闲内存的起始位置。
 */
struct FreeBlock {
    size_t size;            ///< 当前空闲块的总大小（包含 FreeBlock 自身的尺寸）
    size_t next_offset;     ///< 指向下一个 FreeBlock 在 data_region 中的偏移 (0 表示链表尾)
};

/**
 * @brief 对象存储的共享内存布局（支持变长对象和内存回收）
 */
struct ObjectStoreLayout {
    // 容量限制（constexpr = 编译时常量）
    static constexpr int    MAX_OBJECTS       = 1000;             ///< 最大对象数1000
    // 增加数据区大小到 4GB，以支持标准模型
    static constexpr size_t DATA_REGION_SIZE  = 4ULL * 1024 * 1024 * 1024; ///< 4GB

    /**
     * @brief 头部元数据 (增强内存回收功能)
     */
    struct Header {
        // 🚨 注意：全局锁保留，用于保护 Free List 的原子操作
        common::ProcessMutex mutex;        ///< 保护整个 ObjectStore 的锁
        std::atomic<int> object_count;     ///< 当前对象数量
        // Free List 头部：记录第一个 FreeBlock 在 data_region 中的偏移
        std::atomic<size_t> free_list_head_offset;
        char padding[64];                  ///< 缓存行填充
    } header;

    /**
     * @brief 对象槽位（只保存元数据 + data_region 的位置和大小）
     */
    struct ObjectSlot {
        ObjectID id;                        ///< 对象 ID（128 位）
        // 必须是原子操作，以支持无锁扫描
        std::atomic<bool> occupied;         ///< 是否被占用
        size_t offset;                      ///< 在 data_region 中的偏移
        size_t size;                        ///< 数据实际大小

        ObjectSlot()
            : occupied(false), offset(0), size(0) {}
    } slots[MAX_OBJECTS];                   ///< 槽位数组

    /**
     * @brief 数据区：实际存储对象字节内容 (包含 FreeBlock 结构)
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
 * @brief 共享内存对象存储 (增强版：支持 Free List 内存回收)
 */
class ObjectStore {
public:
    explicit ObjectStore(bool create = true);
    ~ObjectStore() = default;

    // ============================================================
    // 核心 API (接口保持不变)
    // ============================================================

    ObjectRef Put(const std::vector<uint8_t>& data);
    ObjectRef Put(const ObjectRef& ref, const std::vector<uint8_t>& data);
    std::shared_ptr<Buffer> Get(const ObjectRef& ref);
    bool Contains(const ObjectRef& ref) const;
    void Delete(const ObjectRef& ref); // 现在会回收 data_region 空间！

    // ============================================================
    // 辅助 API
    // ============================================================

    size_t Size() const;
    static void Cleanup();

private:
    common::SharedMemory shm_;
    ObjectStoreLayout* layout_;

    // ============================================================
    // Free List 内部实现 (供 Put/Delete 调用)
    // ============================================================

    /**
     * @brief 从空闲链表中寻找并分配一个大小合适的块（Best Fit / First Fit）
     * @param size_needed 需要分配的净大小（确保至少能容纳 FreeBlock）
     * @param slot_offset 返回分配到的块在 data_region 中的偏移
     * @return true 成功分配 / false 分配失败
     */
    bool allocate_data_region(size_t size_needed, size_t& slot_offset);

    /**
     * @brief 将释放的块归还给空闲链表，并尝试与相邻块合并（Coalescing）
     * @param offset 释放块的起始偏移
     * @param size 释放块的总大小
     */
    void free_data_region(size_t offset, size_t size);

    /**
     * @brief 尝试合并 Free List 中物理相邻的空闲块（用于减少碎片）
     * 注意：这个函数通常在 free_data_region 内部或周期性调用。
     */
    void coalesce_free_list();
};

}  // namespace object_store
}  // namespace miniray
#pragma once

#include "miniray/shared/shared_memory.h"
#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include "miniray/common/buffer.h"
#include <vector>
#include <cstring>
#include <stdexcept>

namespace miniray {
namespace shared {

/**
 * @brief 共享内存布局 - ObjectStore 部分
 *
 * 简化设计：
 * - 固定数量的对象槽位（1000个）
 * - 每个槽位最大 64KB
 * - 使用线性查找（够简单）
 */
struct SharedObjectStoreLayout {
    // 控制信息
    struct Header {
        ProcessMutex mutex;           // 进程间互斥锁
        std::atomic<int> object_count;  // 当前对象数量
        char padding[64];              // 缓存行对齐
    } header;

    // 对象槽位
    static constexpr int MAX_OBJECTS = 1000;
    static constexpr int MAX_OBJECT_SIZE = 64 * 1024;  // 64 KB

    struct ObjectSlot {
        ObjectID id;                        // 对象 ID
        std::atomic<bool> occupied;         // 是否被占用
        size_t size;                        // 实际数据大小
        uint8_t data[MAX_OBJECT_SIZE];     // 数据

        ObjectSlot() : occupied(false), size(0) {
            // 不初始化 data，节省时间
        }
    } slots[MAX_OBJECTS];

    // 计算总大小
    static constexpr size_t TotalSize() {
        return sizeof(SharedObjectStoreLayout);
    }
};

/**
 * @brief 共享内存对象存储
 *
 * 特点：
 * - 所有进程共享同一块内存
 * - 使用锁保护并发访问
 * - 零拷贝读取（同进程）
 */
class SharedObjectStore {
public:
    /**
     * @brief 构造函数
     *
     * @param create 是否创建（主进程）还是打开（worker 进程）
     */
    explicit SharedObjectStore(bool create = true)
        : shm_("/miniray_objectstore",
               SharedObjectStoreLayout::TotalSize(),
               create) {

        layout_ = static_cast<SharedObjectStoreLayout*>(shm_.GetAddress());

        // 如果是创建模式，初始化头部
        if (create) {
            new (&layout_->header.mutex) ProcessMutex();
            layout_->header.object_count.store(0);

            // 初始化所有槽位
            for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
                new (&layout_->slots[i]) SharedObjectStoreLayout::ObjectSlot();
            }
        }
    }

    ~SharedObjectStore() = default;

    /**
     * @brief 存储对象
     */
    ObjectRef Put(const std::vector<uint8_t>& data) {
        if (data.size() > SharedObjectStoreLayout::MAX_OBJECT_SIZE) {
            throw std::runtime_error("Object too large: " +
                                   std::to_string(data.size()) + " bytes");
        }

        LockGuard lock(layout_->header.mutex);

        // 查找空闲槽位
        int slot_idx = -1;
        for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
            if (!layout_->slots[i].occupied.load()) {
                slot_idx = i;
                break;
            }
        }

        if (slot_idx == -1) {
            throw std::runtime_error("ObjectStore full");
        }

        // 存储对象
        auto& slot = layout_->slots[slot_idx];
        slot.id = ObjectID::FromRandom();
        slot.size = data.size();
        std::memcpy(slot.data, data.data(), data.size());
        slot.occupied.store(true);  // 原子操作，标记为已占用

        layout_->header.object_count.fetch_add(1);

        return ObjectRef(slot.id);
    }

    /**
     * @brief 获取对象
     *
     * 注意：返回的 Buffer 直接指向共享内存
     */
    std::shared_ptr<Buffer> Get(const ObjectRef& ref) {
        LockGuard lock(layout_->header.mutex);

        // 查找对象
        for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
            auto& slot = layout_->slots[i];
            if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
                // 零拷贝：直接引用共享内存中的数据
                return std::make_shared<Buffer>(slot.data, slot.size);
            }
        }

        throw std::runtime_error("Object not found: " + ref.ToHex());
    }

    /**
     * @brief 检查对象是否存在
     */
    bool Contains(const ObjectRef& ref) const {
        // 不需要锁，因为只是读取原子变量
        for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
            auto& slot = layout_->slots[i];
            if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
                return true;
            }
        }
        return false;
    }

    /**
     * @brief 删除对象
     */
    void Delete(const ObjectRef& ref) {
        LockGuard lock(layout_->header.mutex);

        for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
            auto& slot = layout_->slots[i];
            if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
                slot.occupied.store(false);
                layout_->header.object_count.fetch_sub(1);
                return;
            }
        }
    }

    /**
     * @brief 获取对象数量
     */
    size_t Size() const {
        return layout_->header.object_count.load();
    }

    /**
     * @brief 清理共享内存（主进程退出时调用）
     */
    static void Cleanup() {
        SharedMemory::Unlink("/miniray_objectstore");
    }

private:
    SharedMemory shm_;
    SharedObjectStoreLayout* layout_;
};

} // namespace shared
} // namespace miniray

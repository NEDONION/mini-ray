#pragma once

#include "miniray/shared/shared_memory.h"
#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include "miniray/common/buffer.h"

#include <atomic>
#include <vector>
#include <cstring>
#include <stdexcept>

namespace miniray {
namespace shared {

/**
 * @brief 共享内存布局 - ObjectStore 部分
 */
struct SharedObjectStoreLayout {
    struct Header {
        ProcessMutex mutex;
        std::atomic<int> object_count;
        char padding[64];
    } header;

    static constexpr int MAX_OBJECTS = 1000;
    static constexpr int MAX_OBJECT_SIZE = 64 * 1024;  // 64 KB

    struct ObjectSlot {
        ObjectID id;
        std::atomic<bool> occupied;
        size_t size;
        uint8_t data[MAX_OBJECT_SIZE];

        ObjectSlot() : occupied(false), size(0) {}
    } slots[MAX_OBJECTS];

    static constexpr size_t TotalSize() {
        return sizeof(SharedObjectStoreLayout);
    }
};

/**
 * @brief 共享内存对象存储
 */
class SharedObjectStore {
public:
    explicit SharedObjectStore(bool create = true)
        : shm_("/miniray_objectstore",
               SharedObjectStoreLayout::TotalSize(),
               create) {
        layout_ = static_cast<SharedObjectStoreLayout*>(shm_.GetAddress());

        if (create) {
            new (&layout_->header.mutex) ProcessMutex();
            layout_->header.object_count.store(0);

            for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
                new (&layout_->slots[i]) SharedObjectStoreLayout::ObjectSlot();
            }
        }
    }

    ~SharedObjectStore() = default;

    /// 原来的无 ID 版本（如果你还想保留）
    ObjectRef Put(const std::vector<uint8_t>& data) {
        if (data.size() > SharedObjectStoreLayout::MAX_OBJECT_SIZE) {
            throw std::runtime_error("Object too large: " +
                                     std::to_string(data.size()) + " bytes");
        }

        LockGuard lock(layout_->header.mutex);

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

        auto& slot = layout_->slots[slot_idx];
        slot.id = ObjectID::FromRandom();
        slot.size = data.size();
        std::memcpy(slot.data, data.data(), data.size());
        slot.occupied.store(true);

        layout_->header.object_count.fetch_add(1);

        return ObjectRef(slot.id);
    }

    /// ✅ 新增：使用调用方给定的 ObjectRef
    ObjectRef Put(const ObjectRef& ref, const std::vector<uint8_t>& data) {
        if (data.size() > SharedObjectStoreLayout::MAX_OBJECT_SIZE) {
            throw std::runtime_error("Object too large: " +
                                     std::to_string(data.size()) + " bytes");
        }

        LockGuard lock(layout_->header.mutex);

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

        auto& slot = layout_->slots[slot_idx];
        slot.id = ref.GetObjectID();  // 用外部给的 ID
        slot.size = data.size();
        std::memcpy(slot.data, data.data(), data.size());
        slot.occupied.store(true);

        layout_->header.object_count.fetch_add(1);

        return ObjectRef(slot.id);  // == ref
    }

    std::shared_ptr<Buffer> Get(const ObjectRef& ref) {
        LockGuard lock(layout_->header.mutex);

        for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
            auto& slot = layout_->slots[i];
            if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
                return std::make_shared<Buffer>(slot.data, slot.size);
            }
        }

        throw std::runtime_error("Object not found: " + ref.ToHex());
    }

    bool Contains(const ObjectRef& ref) const {
        for (int i = 0; i < SharedObjectStoreLayout::MAX_OBJECTS; i++) {
            auto& slot = layout_->slots[i];
            if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
                return true;
            }
        }
        return false;
    }

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

    size_t Size() const {
        return layout_->header.object_count.load();
    }

    static void Cleanup() {
        SharedMemory::Unlink("/miniray_objectstore");
    }

private:
    SharedMemory shm_;
    SharedObjectStoreLayout* layout_;
};

}  // namespace shared
}  // namespace miniray

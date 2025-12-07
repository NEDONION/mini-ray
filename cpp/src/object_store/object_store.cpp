/**
 * object_store.cpp - 对象存储实现（v2：变长对象版本）
 */

#include "miniray/object_store/object_store.h"

namespace miniray {
namespace object_store {

// ============================================================
// ObjectStore 实现
// ============================================================

ObjectStore::ObjectStore(bool create)
    : shm_("/miniray_objectstore",
           ObjectStoreLayout::TotalSize(),
           create) {

    // 获取共享内存布局指针
    layout_ = static_cast<ObjectStoreLayout*>(shm_.GetAddress());

    if (create) {
        // 创建模式：初始化共享内存中的所有对象

        // 在共享内存中构造互斥锁
        new (&layout_->header.mutex) common::ProcessMutex();

        // 初始化计数器和 data_region 偏移
        layout_->header.object_count.store(0);
        layout_->header.data_offset.store(0);

        // 初始化所有槽位（placement new，保证构造函数被调用）
        for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
            new (&layout_->slots[i]) ObjectStoreLayout::ObjectSlot();
        }

        // data_region 不需要特别清零（按需写入）
    }
}

ObjectRef ObjectStore::Put(const std::vector<uint8_t>& data) {
    // 空对象允许，但意义不大，这里只禁止超过数据区总大小的对象
    if (data.size() > ObjectStoreLayout::DATA_REGION_SIZE) {
        throw std::runtime_error("Object too large: " +
                                 std::to_string(data.size()) + " bytes");
    }

    // 粗粒度加锁，保护 header / slots / data_region
    common::LockGuard lock(layout_->header.mutex);

    // 1) 在数据区中分配空间（简单 bump allocator）
    size_t cur_offset = layout_->header.data_offset.load(std::memory_order_relaxed);
    size_t new_offset = cur_offset + data.size();

    if (new_offset > ObjectStoreLayout::DATA_REGION_SIZE) {
        throw std::runtime_error("ObjectStore data_region full");
    }

    // 2) 找一个空闲槽位
    int slot_idx = -1;
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        if (!layout_->slots[i].occupied.load(std::memory_order_acquire)) {
            slot_idx = i;
            break;
        }
    }

    if (slot_idx == -1) {
        throw std::runtime_error("ObjectStore full (no free slots)");
    }

    // 3) 填充槽位元数据
    auto& slot = layout_->slots[slot_idx];
    slot.id     = ObjectID::FromRandom();
    slot.offset = cur_offset;
    slot.size   = data.size();

    // 4) 写入数据到 data_region
    if (!data.empty()) {
        std::memcpy(layout_->data_region + cur_offset,
                    data.data(),
                    data.size());
    }

    // 5) 标记占用 & 更新计数器/偏移
    slot.occupied.store(true, std::memory_order_release);
    layout_->header.object_count.fetch_add(1, std::memory_order_relaxed);
    layout_->header.data_offset.store(new_offset, std::memory_order_relaxed);

    // 6) 返回 ObjectRef
    return ObjectRef(slot.id);
}

ObjectRef ObjectStore::Put(const ObjectRef& ref, const std::vector<uint8_t>& data) {
    if (data.size() > ObjectStoreLayout::DATA_REGION_SIZE) {
        throw std::runtime_error("Object too large: " +
                                 std::to_string(data.size()) + " bytes");
    }

    common::LockGuard lock(layout_->header.mutex);

    // 1) 分配 data_region 空间
    size_t cur_offset = layout_->header.data_offset.load(std::memory_order_relaxed);
    size_t new_offset = cur_offset + data.size();

    if (new_offset > ObjectStoreLayout::DATA_REGION_SIZE) {
        throw std::runtime_error("ObjectStore data_region full");
    }

    // 2) 找空槽位
    int slot_idx = -1;
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        if (!layout_->slots[i].occupied.load(std::memory_order_acquire)) {
            slot_idx = i;
            break;
        }
    }

    if (slot_idx == -1) {
        throw std::runtime_error("ObjectStore full (no free slots)");
    }

    // 3) 填槽位（使用调用方提供的 ID）
    auto& slot = layout_->slots[slot_idx];
    slot.id     = ref.GetObjectID();
    slot.offset = cur_offset;
    slot.size   = data.size();

    if (!data.empty()) {
        std::memcpy(layout_->data_region + cur_offset,
                    data.data(),
                    data.size());
    }

    slot.occupied.store(true, std::memory_order_release);
    layout_->header.object_count.fetch_add(1, std::memory_order_relaxed);
    layout_->header.data_offset.store(new_offset, std::memory_order_relaxed);

    return ObjectRef(slot.id);  // 和 ref 逻辑上相同
}

std::shared_ptr<Buffer> ObjectStore::Get(const ObjectRef& ref) {
    common::LockGuard lock(layout_->header.mutex);

    const ObjectID& target_id = ref.GetObjectID();

    // 线性扫描槽位（教学版设计）
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load(std::memory_order_acquire) &&
            slot.id == target_id) {

            // 边界检查（防止写坏 data_region 时造成越界）
            if (slot.offset + slot.size > ObjectStoreLayout::DATA_REGION_SIZE) {
                throw std::runtime_error("Corrupted slot: offset+size out of range");
            }

            // 从 data_region 拷贝到 Buffer
            const uint8_t* src = layout_->data_region + slot.offset;
            return std::make_shared<Buffer>(src, slot.size);
        }
    }

    throw std::runtime_error("Object not found: " + ref.ToHex());
}

bool ObjectStore::Contains(const ObjectRef& ref) const {
    // 无锁 hint：只读 occupied + id
    const ObjectID& target_id = ref.GetObjectID();

    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load(std::memory_order_acquire) &&
            slot.id == target_id) {
            return true;
        }
    }
    return false;
}

void ObjectStore::Delete(const ObjectRef& ref) {
    common::LockGuard lock(layout_->header.mutex);

    const ObjectID& target_id = ref.GetObjectID();

    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load(std::memory_order_acquire) &&
            slot.id == target_id) {

            // 简化版本：只标记未占用，不回收 data_region 空间
            slot.occupied.store(false, std::memory_order_release);
            layout_->header.object_count.fetch_sub(1, std::memory_order_relaxed);
            return;
        }
    }
    // 不存在就静默返回（幂等）
}

size_t ObjectStore::Size() const {
    return static_cast<size_t>(
        layout_->header.object_count.load(std::memory_order_relaxed));
}

void ObjectStore::Cleanup() {
    common::SharedMemory::Unlink("/miniray_objectstore");
}

}  // namespace object_store
}  // namespace miniray

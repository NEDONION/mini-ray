/**
 * object_store.cpp - 对象存储实现
 *
 * 本文件实现了 object_store.h 中声明的 ObjectStore 类
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
    // static_cast 将 void* 转换为 ObjectStoreLayout*
    layout_ = static_cast<ObjectStoreLayout*>(shm_.GetAddress());

    if (create) {
        // 创建模式：初始化共享内存中的所有对象

        // placement new: 在共享内存中构造 ProcessMutex
        // 语法：new (地址) 类型(参数)
        new (&layout_->header.mutex) common::ProcessMutex();

        // 原子变量可以直接赋值（等价于 store）
        layout_->header.object_count.store(0);

        // 初始化所有槽位
        // 注意：必须使用 placement new，因为 ObjectSlot 有非平凡构造函数
        for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
            new (&layout_->slots[i]) ObjectStoreLayout::ObjectSlot();
        }
    }
}

ObjectRef ObjectStore::Put(const std::vector<uint8_t>& data) {
    // 检查数据大小
    if (data.size() > ObjectStoreLayout::MAX_OBJECT_SIZE) {
        throw std::runtime_error("Object too large: " +
                                 std::to_string(data.size()) + " bytes");
    }

    // RAII 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 线性搜索空闲槽位
    int slot_idx = -1;
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        // load() 原子读取
        if (!layout_->slots[i].occupied.load()) {
            slot_idx = i;
            break;
        }
    }

    // 检查是否找到空闲槽位
    if (slot_idx == -1) {
        throw std::runtime_error("ObjectStore full");
    }

    // 填充槽位
    auto& slot = layout_->slots[slot_idx];
    slot.id = ObjectID::FromRandom();           // 生成随机 ID
    slot.size = data.size();                    // 记录大小
    std::memcpy(slot.data, data.data(), data.size());  // 拷贝数据
    slot.occupied.store(true);                  // 标记为占用（原子操作）

    // 增加计数器
    // fetch_add(1) 原子地执行：old_value = counter; counter++; return old_value;
    layout_->header.object_count.fetch_add(1);

    // 返回 ObjectRef
    return ObjectRef(slot.id);
}

ObjectRef ObjectStore::Put(const ObjectRef& ref, const std::vector<uint8_t>& data) {
    // 检查数据大小
    if (data.size() > ObjectStoreLayout::MAX_OBJECT_SIZE) {
        throw std::runtime_error("Object too large: " +
                                 std::to_string(data.size()) + " bytes");
    }

    // RAII 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 查找空闲槽位
    int slot_idx = -1;
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        if (!layout_->slots[i].occupied.load()) {
            slot_idx = i;
            break;
        }
    }

    if (slot_idx == -1) {
        throw std::runtime_error("ObjectStore full");
    }

    // 填充槽位（使用调用方提供的 ID）
    auto& slot = layout_->slots[slot_idx];
    slot.id = ref.GetObjectID();                // 使用外部 ID
    slot.size = data.size();
    std::memcpy(slot.data, data.data(), data.size());
    slot.occupied.store(true);

    layout_->header.object_count.fetch_add(1);

    return ObjectRef(slot.id);  // 返回的 ObjectRef 与输入相同
}

std::shared_ptr<Buffer> ObjectStore::Get(const ObjectRef& ref) {
    // 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 线性搜索匹配的 ObjectID
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
            // 找到对象，拷贝到新的 Buffer
            // Buffer 构造函数会拷贝数据
            return std::make_shared<Buffer>(slot.data, slot.size);
        }
    }

    // 对象不存在
    throw std::runtime_error("Object not found: " + ref.ToHex());
}

bool ObjectStore::Contains(const ObjectRef& ref) const {
    // 注意：没有加锁（性能优化）
    // 仅用于 hint，不保证强一致性

    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
            return true;
        }
    }
    return false;
}

void ObjectStore::Delete(const ObjectRef& ref) {
    // 加锁
    common::LockGuard lock(layout_->header.mutex);

    // 查找并删除
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load() && slot.id == ref.GetObjectID()) {
            slot.occupied.store(false);  // 标记为未占用
            layout_->header.object_count.fetch_sub(1);  // 减少计数
            return;
        }
    }

    // 对象不存在，静默返回（幂等性）
}

size_t ObjectStore::Size() const {
    // 原子读取，不需要加锁
    return layout_->header.object_count.load();
}

void ObjectStore::Cleanup() {
    // 删除共享内存对象
    common::SharedMemory::Unlink("/miniray_objectstore");
}

}  // namespace object_store
}  // namespace miniray

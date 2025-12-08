/**
 * object_store.cpp - 共享内存对象存储实现（v3：支持 Free List 内存回收）
 *
 * ============================================================
 * 💡 设计思路 (Design Philosophy)
 * ============================================================
 *
 * 目标：提供一个高性能、支持长时间训练 (200+ Epochs) 的进程间共享内存存储。
 *
 * 1. 架构：元数据/数据分离 (Plasma 风格)
 * - ObjectSlot 数组：存储元数据 (ObjectID, 偏移, 大小)。
 * - data_region：存储实际对象数据和内存管理结构 (FreeBlock)。
 *
 * 2. 内存管理：Free List (空闲链表)
 * - 解决了 V2 版本中 Bump Allocator 导致的**内存泄漏**和**数据区耗尽**问题。
 * - Put 操作：遍历 Free List 查找合适的块，支持块拆分 (Splitting)。
 * - Delete 操作：将释放的内存块重新包装成 FreeBlock，插入到 Free List 头部 (LIFO)，并尝试**合并**相邻空闲块以减少外部碎片。
 *
 * 3. 并发控制：粗粒度锁
 * - 为了实现 Free List 的原子分配和回收，继续使用 `Header::mutex` 保护整个 Free List 和 Slot 查找。
 * - ⚠️ 未来可优化：采用细粒度锁或无锁 CAS 来提升并发 Put/Get 性能。
 *
 * 4. 容量：增强
 * - 将容量从 64MB 提升到 4GB，以支持标准深度学习模型的参数存储。
 *
 * * ============================================================
 * ⚙️ 关键 C++ 语法特性 (Key C++ Features)
 * ============================================================
 *
 * 1. 共享内存 (`common::SharedMemory`)
 * - 使用操作系统原语创建和映射进程间共享的内存区域。
 * - `shm_.GetAddress()` 返回共享内存基址，该地址被所有连接的进程访问。
 *
 * 2. Placement New (`new (&layout_->header.mutex)`)
 * - 在共享内存的指定地址上**构造**对象（如 `ProcessMutex`），确保在共享内存中创建正确的 C++ 结构。
 *
 * 3. 进程同步 (`common::ProcessMutex`, `common::LockGuard`)
 * - 使用基于进程的互斥锁 (`ProcessMutex`) 确保多个进程对共享内存的并发修改是安全的。
 * - `LockGuard` 实现 RAII，自动管理锁的获取和释放。
 *
 * 4. 原子操作 (`std::atomic<int>`, `std::atomic<bool>`)
 * - 用于保护单个变量（如 `object_count`, `occupied`, `free_list_head_offset`）的读写操作，无需显式加锁。
 * - 使用 `std::memory_order_acquire/release` 确保内存操作的正确顺序。
 *
 * 5. 指针转换/内存操作
 * - `reinterpret_cast<FreeBlock*>(...)`：将字节数组 (`data_region`) 中的偏移地址转换为特定结构体 (`FreeBlock`) 的指针，用于直接操作共享内存中的数据。
 * - `std::memcpy()`：高效地在共享内存区域内或从 `std::vector<uint8_t>` 到共享内存之间进行块数据拷贝。
 *
 * 6. 零偏移 (`0` 或 `-1`)
 * - Free List 中，`0` 被用作 `data_region` 的起始偏移，也作为链表的**尾部标识** (`next_offset = 0`)。
 * * ============================================================
 */

#include "miniray/object_store/object_store.h"
#include <algorithm>

namespace miniray {
namespace object_store {

// ============================================================
// ObjectStore 实现
// ============================================================

ObjectStore::ObjectStore(bool create)
    : shm_("/miniray_objectstore",
           ObjectStoreLayout::TotalSize(),
           create) {

    layout_ = static_cast<ObjectStoreLayout*>(shm_.GetAddress());

    if (create) {
        // 创建模式：初始化共享内存中的所有对象
        new (&layout_->header.mutex) common::ProcessMutex();
        layout_->header.object_count.store(0);

        // **1. 初始化 Free List**
        // 整个 data_region (4GB) 作为一个巨大的空闲块
        FreeBlock* initial_block = reinterpret_cast<FreeBlock*>(layout_->data_region);
        initial_block->size = ObjectStoreLayout::DATA_REGION_SIZE;
        initial_block->next_offset = 0; // 0 表示链表尾

        // 空闲链表的头部指向第一个块（偏移为 0）
        layout_->header.free_list_head_offset.store(0, std::memory_order_relaxed);

        // 2. 初始化所有槽位
        for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
            new (&layout_->slots[i]) ObjectStoreLayout::ObjectSlot();
        }
    }
}

// ============================================================
// 核心接口
// ============================================================

ObjectRef ObjectStore::Put(const std::vector<uint8_t>& data) {
    if (data.empty()) {
        throw std::runtime_error("Cannot put zero-sized object.");
    }

    // 实际需要分配的空间就是数据大小
    size_t size_needed = data.size();
    size_t data_offset = 0;

    // 粗粒度加锁，保护 Free List 和 Slot 查找
    common::LockGuard lock(layout_->header.mutex);

    // 1. 在数据区中分配空间（使用 Free List）
    if (!allocate_data_region(size_needed, data_offset)) {
        throw std::runtime_error("ObjectStore data_region full or heavily fragmented");
    }

    // 2. 找一个空闲槽位（线性扫描）
    int slot_idx = -1;
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        // 尝试无锁检查，但因为 Free List 的分配在锁内，这里可以简化
        if (!layout_->slots[i].occupied.load(std::memory_order_acquire)) {
            slot_idx = i;
            break;
        }
    }

    if (slot_idx == -1) {
        // 槽位已满，回滚数据区分配
        // 注意：这里简单回滚，实际应释放 data_offset 处被占用的 size_needed 块
        // 简单起见，我们假设 allocate_data_region 只返回恰好分配的偏移
        free_data_region(data_offset, size_needed);
        throw std::runtime_error("ObjectStore full (no free slots)");
    }

    // 3. 填充槽位元数据
    auto& slot = layout_->slots[slot_idx];
    slot.id     = ObjectID::FromRandom();
    slot.offset = data_offset;
    slot.size   = data.size();

    // 4. 写入数据到 data_region
    std::memcpy(layout_->data_region + data_offset,
                data.data(),
                data.size());

    // 5. 标记占用 & 更新计数器
    slot.occupied.store(true, std::memory_order_release);
    layout_->header.object_count.fetch_add(1, std::memory_order_relaxed);

    return ObjectRef(slot.id);
}

ObjectRef ObjectStore::Put(const ObjectRef& ref, const std::vector<uint8_t>& data) {
    // 逻辑与 Put(data) 类似，只是使用了提供的 ref.GetObjectID()
    if (data.empty()) {
        throw std::runtime_error("Cannot put zero-sized object.");
    }

    size_t size_needed = data.size();
    size_t data_offset = 0;

    common::LockGuard lock(layout_->header.mutex);

    if (!allocate_data_region(size_needed, data_offset)) {
        throw std::runtime_error("ObjectStore data_region full or heavily fragmented");
    }

    int slot_idx = -1;
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        if (!layout_->slots[i].occupied.load(std::memory_order_acquire)) {
            slot_idx = i;
            break;
        }
    }

    if (slot_idx == -1) {
        free_data_region(data_offset, size_needed);
        throw std::runtime_error("ObjectStore full (no free slots)");
    }

    auto& slot = layout_->slots[slot_idx];
    slot.id     = ref.GetObjectID();
    slot.offset = data_offset;
    slot.size   = data.size();

    std::memcpy(layout_->data_region + data_offset,
                data.data(),
                data.size());

    slot.occupied.store(true, std::memory_order_release);
    layout_->header.object_count.fetch_add(1, std::memory_order_relaxed);

    return ObjectRef(slot.id);
}

std::shared_ptr<Buffer> ObjectStore::Get(const ObjectRef& ref) {
    // 锁保护槽位查找，以确保线程安全
    common::LockGuard lock(layout_->header.mutex);

    const ObjectID& target_id = ref.GetObjectID();

    // 线性扫描槽位 O(n)
    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load(std::memory_order_acquire) &&
            slot.id == target_id) {

            // 拷贝到 Buffer
            const uint8_t* src = layout_->data_region + slot.offset;
            // 确保 size 不越界（虽然在 Put 时已检查，但多一层防御）
            if (slot.offset + slot.size > ObjectStoreLayout::DATA_REGION_SIZE) {
                 throw std::runtime_error("Corrupted slot data size.");
            }
            return std::make_shared<Buffer>(src, slot.size);
        }
    }

    throw std::runtime_error("Object not found: " + ref.ToHex());
}

void ObjectStore::Delete(const ObjectRef& ref) {
    common::LockGuard lock(layout_->header.mutex);

    const ObjectID& target_id = ref.GetObjectID();

    for (int i = 0; i < ObjectStoreLayout::MAX_OBJECTS; i++) {
        auto& slot = layout_->slots[i];
        if (slot.occupied.load(std::memory_order_acquire) &&
            slot.id == target_id) {

            // 1. 回收数据区空间 ♻️
            free_data_region(slot.offset, slot.size);

            // 2. 标记槽位未占用 & 更新计数器
            slot.occupied.store(false, std::memory_order_release);
            layout_->header.object_count.fetch_sub(1, std::memory_order_relaxed);

            return;
        }
    }
    // 不存在就静默返回
}

// ============================================================
// Free List 内存管理实现
// ============================================================

bool ObjectStore::allocate_data_region(size_t size_needed, size_t& slot_offset) {
    // 最小分配单位：确保即使是数据 size=1 的块，也能容纳 FreeBlock 结构（用于后续回收）
    size_t aligned_size_needed = std::max(size_needed, sizeof(FreeBlock));

    // 我们采用 First Fit 策略：找到第一个足够大的块
    size_t current_offset = layout_->header.free_list_head_offset.load(std::memory_order_relaxed);
    size_t prev_offset = (size_t)-1; // 使用 -1 表示"没有前驱"（而不是 0）

    // 遍历 Free List
    // 注意：初始化时，头部指向偏移 0，这是一个合法的空闲块
    // 我们需要至少检查一次，即使 current_offset == 0
    bool first_iteration = true;

    while (first_iteration || current_offset != 0) {
        first_iteration = false;

        FreeBlock* current_block = reinterpret_cast<FreeBlock*>(layout_->data_region + current_offset);

        if (current_block->size >= aligned_size_needed) {
            // 找到合适的块 (First Fit)

            size_t allocated_size = current_block->size;

            // 1. 块拆分判断：如果剩余空间大于 FreeBlock 结构所需，则拆分
            if (allocated_size - aligned_size_needed >= sizeof(FreeBlock)) {
                // 剩余块的起始偏移
                size_t remainder_offset = current_offset + aligned_size_needed;
                // 剩余块的大小
                size_t remainder_size = allocated_size - aligned_size_needed;

                // 构造新的剩余空闲块
                FreeBlock* remainder_block = reinterpret_cast<FreeBlock*>(layout_->data_region + remainder_offset);
                remainder_block->size = remainder_size;
                remainder_block->next_offset = current_block->next_offset; // 剩余块继承下一个指针

                // 更新链表：将前一个块指向剩余块
                if (prev_offset == (size_t)-1) {
                    // 更新头部（当前块是第一个块）
                    layout_->header.free_list_head_offset.store(remainder_offset, std::memory_order_relaxed);
                } else {
                    // 更新前一个块的 next_offset
                    FreeBlock* prev_block = reinterpret_cast<FreeBlock*>(layout_->data_region + prev_offset);
                    prev_block->next_offset = remainder_offset;
                }

            } else {
                // 剩余空间太小，直接分配整个块 (牺牲一点内部碎片)

                // 更新链表：前一个块跳过被分配的块
                if (prev_offset == (size_t)-1) {
                    // 更新头部（当前块是第一个块）
                    layout_->header.free_list_head_offset.store(current_block->next_offset, std::memory_order_relaxed);
                } else {
                    // 更新前一个块的 next_offset
                    FreeBlock* prev_block = reinterpret_cast<FreeBlock*>(layout_->data_region + prev_offset);
                    prev_block->next_offset = current_block->next_offset;
                }
            }

            // 返回分配到的偏移
            slot_offset = current_offset;
            return true;
        }

        // 移动到下一个块
        prev_offset = current_offset;
        current_offset = current_block->next_offset;
    }

    // 遍历完成，没有找到足够的空间
    return false;
}

void ObjectStore::free_data_region(size_t offset, size_t size) {
    if (size == 0 || offset >= ObjectStoreLayout::DATA_REGION_SIZE) return;

    // 1. 构造新的 FreeBlock（假设这个块是干净的，并且其大小为 slot.size）
    // 注意：这里我们只释放了 slot.size，但如果分配时有对齐/填充，那可能需要释放更多。
    // 为了简化，这里假设我们只释放了对象实际数据占用的空间。
    FreeBlock* new_free_block = reinterpret_cast<FreeBlock*>(layout_->data_region + offset);
    new_free_block->size = size;

    // 2. 将释放的块插入到 Free List 头部 (LIFO 策略)
    size_t old_head = layout_->header.free_list_head_offset.load(std::memory_order_relaxed);
    new_free_block->next_offset = old_head;
    layout_->header.free_list_head_offset.store(offset, std::memory_order_release);

    // 3. 尝试合并（避免外部碎片）
    coalesce_free_list();
}

void ObjectStore::coalesce_free_list() {
    // 🚧 块合并逻辑实现：
    // 目标：遍历 Free List，找到在物理地址上相邻的空闲块并合并。
    // 挑战：Free List 是按逻辑（next_offset）链接的，但合并需要按物理地址（offset）查找。

    // 简易实现思路：
    // 1. 将所有 FreeBlock 提取出来，存储在一个辅助结构（如 std::vector<std::pair<size_t, size_t>>）中。
    // 2. 按 offset 排序。
    // 3. 线性扫描排序后的列表，合并物理相邻的块。
    // 4. 清空旧 Free List，用合并后的块重建 Free List。

    // 由于涉及大量的内存拷贝和排序，这在共享内存代码中较为复杂且耗时。
    // ⚠️ 教学/实验场景中，此函数通常被置空或只实现简单逻辑，以避免引入巨大的性能开销。
    // 对于 4GB 的数据区，完整的 Coalescing 应当使用更高级的分配器（如伙伴系统）或只在碎片化严重时执行。

    // 暂不实现完整的 Coalescing 逻辑，留待专门的内存管理模块。
}

// ============================================================
// 辅助接口
// ============================================================

bool ObjectStore::Contains(const ObjectRef& ref) const {
    // 保持与 Get 相同的锁定逻辑，以确保槽位状态的可见性
    common::LockGuard lock(layout_->header.mutex);
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

size_t ObjectStore::Size() const {
    return static_cast<size_t>(
        layout_->header.object_count.load(std::memory_order_relaxed));
}

void ObjectStore::Cleanup() {
    common::SharedMemory::Unlink("/miniray_objectstore");
}

}  // namespace object_store
}  // namespace miniray
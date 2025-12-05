#pragma once

#include "miniray/common/object_ref.h"
#include <unordered_map>
#include <vector>
#include <memory>
#include <mutex>
#include <stdexcept>

namespace miniray {

/**
 * @brief Buffer 封装了对象的原始数据
 */
class Buffer {
public:
    Buffer(const uint8_t* data, size_t size) {
        data_.resize(size);
        std::memcpy(data_.data(), data, size);
    }

    explicit Buffer(const std::vector<uint8_t>& data) : data_(data) {}

    const uint8_t* Data() const { return data_.data(); }
    size_t Size() const { return data_.size(); }

    std::vector<uint8_t> ToVector() const { return data_; }

private:
    std::vector<uint8_t> data_;
};

/**
 * @brief ObjectStore 管理对象存储
 *
 * Phase 1: 简单的内存版本（std::unordered_map）
 * Phase 2: 升级到共享内存版本（boost::interprocess）
 */
class ObjectStore {
public:
    ObjectStore() = default;
    ~ObjectStore() = default;

    /**
     * @brief 存储对象，返回 ObjectRef
     */
    ObjectRef Put(const std::vector<uint8_t>& data) {
        ObjectRef ref;
        auto buffer = std::make_shared<Buffer>(data);

        std::lock_guard<std::mutex> lock(mutex_);
        objects_[ref.GetObjectID()] = buffer;

        return ref;
    }

    /**
     * @brief 根据 ObjectRef 获取对象
     *
     * @throws std::runtime_error 如果对象不存在
     */
    std::shared_ptr<Buffer> Get(const ObjectRef& ref) {
        std::lock_guard<std::mutex> lock(mutex_);

        auto it = objects_.find(ref.GetObjectID());
        if (it == objects_.end()) {
            throw std::runtime_error("Object not found: " + ref.ToString());
        }

        return it->second;
    }

    /**
     * @brief 删除对象
     */
    void Delete(const ObjectRef& ref) {
        std::lock_guard<std::mutex> lock(mutex_);
        objects_.erase(ref.GetObjectID());
    }

    /**
     * @brief 检查对象是否存在
     */
    bool Contains(const ObjectRef& ref) const {
        std::lock_guard<std::mutex> lock(mutex_);
        return objects_.find(ref.GetObjectID()) != objects_.end();
    }

    /**
     * @brief 获取存储的对象数量
     */
    size_t Size() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return objects_.size();
    }

private:
    // 对象映射：ObjectID -> Buffer
    std::unordered_map<ObjectID, std::shared_ptr<Buffer>> objects_;

    // 线程安全保护
    mutable std::mutex mutex_;
};

} // namespace miniray

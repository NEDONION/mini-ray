#pragma once

#include <vector>
#include <cstring>
#include <memory>

namespace miniray {

/**
 * @brief Buffer 封装了对象的原始数据
 *
 * 简单的数据缓冲区，用于存储序列化的对象
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

}  // namespace miniray

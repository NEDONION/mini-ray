#pragma once

#include <array>
#include <cstring>
#include <random>
#include <string>
#include <sstream>
#include <iomanip>

namespace miniray {

/**
 * @brief 128-bit 唯一标识符（类似 UUID）
 *
 * 用于标识 ObjectRef、TaskID、WorkerID 等
 */
class ObjectID {
public:
    static constexpr size_t kLength = 16;  // 128 bits

    /**
     * @brief 默认构造函数（全零）
     */
    ObjectID() {
        data_.fill(0);
    }

    /**
     * @brief 从字节数组构造
     */
    explicit ObjectID(const uint8_t* bytes) {
        std::memcpy(data_.data(), bytes, kLength);
    }

    /**
     * @brief 生成随机 ObjectID
     */
    static ObjectID FromRandom() {
        ObjectID id;
        std::random_device rd;
        std::mt19937_64 gen(rd());
        std::uniform_int_distribution<uint64_t> dis;

        // 生成 16 字节随机数据
        uint64_t* ptr = reinterpret_cast<uint64_t*>(id.data_.data());
        ptr[0] = dis(gen);
        ptr[1] = dis(gen);

        return id;
    }

    /**
     * @brief 从十六进制字符串创建 ObjectID
     */
    static ObjectID FromHex(const std::string& hex_string) {
        ObjectID id;
        if (hex_string.length() != kLength * 2) {
            throw std::invalid_argument("Invalid hex string length");
        }

        for (size_t i = 0; i < kLength; ++i) {
            std::string byte_str = hex_string.substr(i * 2, 2);
            id.data_[i] = static_cast<uint8_t>(std::stoi(byte_str, nullptr, 16));
        }

        return id;
    }

    /**
     * @brief 转换为十六进制字符串
     */
    std::string ToHex() const {
        std::ostringstream oss;
        oss << std::hex << std::setfill('0');
        for (size_t i = 0; i < kLength; ++i) {
            oss << std::setw(2) << static_cast<int>(data_[i]);
        }
        return oss.str();
    }

    /**
     * @brief 获取原始字节数据
     */
    const uint8_t* Data() const {
        return data_.data();
    }

    /**
     * @brief 比较运算符（用于 unordered_map）
     */
    bool operator==(const ObjectID& other) const {
        return data_ == other.data_;
    }

    bool operator!=(const ObjectID& other) const {
        return !(*this == other);
    }

    /**
     * @brief 判断是否为空（全零）
     */
    bool IsNil() const {
        for (uint8_t byte : data_) {
            if (byte != 0) return false;
        }
        return true;
    }

private:
    std::array<uint8_t, kLength> data_;
};

// 为了在 unordered_map 中使用 ObjectID，需要提供 hash 函数
} // namespace miniray

namespace std {
template <>
struct hash<miniray::ObjectID> {
    size_t operator()(const miniray::ObjectID& id) const {
        // 简单的 hash：使用前 8 字节
        size_t result = 0;
        const uint8_t* data = id.Data();
        std::memcpy(&result, data, sizeof(size_t));
        return result;
    }
};
} // namespace std

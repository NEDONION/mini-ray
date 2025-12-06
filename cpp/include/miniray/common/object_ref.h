#pragma once

#include "miniray/common/id.h"
#include <string>

namespace miniray {

/**
 * @brief ObjectRef 表示一个远程对象的引用
 *
 * 类似于 Future/Promise，用于异步获取任务的返回值
 */
class ObjectRef {
public:
    /**
     * @brief 默认构造函数（生成随机 ObjectID）
     */
    ObjectRef() : object_id_(ObjectID::FromRandom()) {}

    /**
     * @brief 从 ObjectID 构造
     */
    explicit ObjectRef(const ObjectID& object_id) : object_id_(object_id) {}

    /**
     * @brief 获取 ObjectID
     */
    const ObjectID& GetObjectID() const {
        return object_id_;
    }

    /**
     * @brief 获取 ObjectID
     */
    const ObjectID& ID() const {
        return object_id_;
    }

    /**
     * @brief 获取 ObjectID 的十六进制表示
     */
    std::string ToHex() const {
        return object_id_.ToHex();
    }

    /**
     * @brief 转换为字符串（用于调试和 Python 绑定）
     */
    std::string ToString() const {
        return "ObjectRef(" + object_id_.ToHex().substr(0, 8) + "...)";
    }

    /**
     * @brief 比较运算符
     */
    bool operator==(const ObjectRef& other) const {
        return object_id_ == other.object_id_;
    }

    bool operator!=(const ObjectRef& other) const {
        return !(*this == other);
    }

private:
    ObjectID object_id_;
};

} // namespace miniray

namespace std {
template <>
struct hash<miniray::ObjectRef> {
    size_t operator()(const miniray::ObjectRef& ref) const {
        return std::hash<miniray::ObjectID>()(ref.GetObjectID());
    }
};
} // namespace std

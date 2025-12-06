#pragma once

#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include <vector>
#include <string>

namespace miniray {

using TaskID = ObjectID;
using FunctionID = ObjectID;

/**
 * @brief Task 表示一个待执行的任务
 */
struct Task {
    TaskID task_id;
    FunctionID function_id;

    // 返回值的 ObjectRef
    ObjectRef return_ref;

    // 序列化的函数体（Python pickle 数据）
    std::vector<uint8_t> serialized_function;

    // 序列化的参数（Python pickle 数据）
    std::vector<uint8_t> serialized_args;

    Task() : task_id(ObjectID::FromRandom()),
             function_id(ObjectID::FromRandom()),
             return_ref(ObjectRef()) {}
};

} // namespace miniray

#pragma once

#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include <vector>
#include <string>

namespace miniray {

using TaskID = ObjectID;
using FunctionID = ObjectID;

/**
 * @brief TaskSpec 定义了任务的规格
 */
struct TaskSpec {
    TaskID task_id;
    FunctionID function_id;

    // 序列化的函数体（Python pickle 数据）
    std::vector<uint8_t> serialized_function;

    // 序列化的参数（Python pickle 数据）
    std::vector<uint8_t> serialized_args;

    TaskSpec() : task_id(ObjectID::FromRandom()),
                 function_id(ObjectID::FromRandom()) {}
};

/**
 * @brief Task 表示一个待执行的任务
 */
struct Task {
    TaskSpec task_spec;
    ObjectRef return_ref;  // 返回值的 ObjectRef

    Task() : return_ref(ObjectRef()) {}

    explicit Task(const TaskSpec& spec)
        : task_spec(spec), return_ref(ObjectRef()) {}
};

} // namespace miniray

/**
 * python_bindings.cpp - Python/C++ 绑定层
 *
 * 这个文件的作用：
 * 使用 pybind11 库将 C++ 类和函数暴露给 Python，让 Python 代码可以调用 C++ 实现。
 *
 * 核心概念：
 * 1. pybind11：一个轻量级的 C++/Python 绑定库
 * 2. PYBIND11_MODULE：定义一个 Python 模块（编译后生成 _miniray_core.so）
 * 3. py::class_<T>：将 C++ 类 T 暴露为 Python 类
 * 4. .def()：定义 Python 可调用的方法
 * 5. lambda：用于类型转换（C++ ↔ Python）
 *
 * 编译后生成：
 *   - macOS/Linux: _miniray_core.so
 *   - Windows: _miniray_core.pyd
 *
 * Python 使用：
 *   import _miniray_core
 *   store = _miniray_core.ObjectStore()
 *   ref = store.put(b"data")
 */

#include <pybind11/pybind11.h>      // pybind11 核心头文件
#include <pybind11/stl.h>           // STL 容器支持（vector, map 等）
#include <pybind11/operators.h>     // 运算符重载支持（==, !=, <, > 等）

// Mini-Ray 核心头文件
#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include "miniray/common/task.h"
#include "miniray/object_store/object_store.h"

namespace py = pybind11;            // 简化命名空间
using namespace miniray;

/**
 * PYBIND11_MODULE 宏定义
 *
 * 参数说明：
 *   - _miniray_core: 模块名称（必须与 CMakeLists.txt 中的名称一致）
 *   - m: 模块对象（用于添加类、函数等）
 *
 * 这个宏会生成 Python 模块的入口函数，Python 导入时会调用这个函数。
 */
PYBIND11_MODULE(_miniray_core, m) {
    // 模块文档字符串（Python 中通过 help(_miniray_core) 查看）
    m.doc() = "Mini-Ray C++ Core Module - High-performance distributed computing primitives";

    // ============================================================
    // ObjectID - 128-bit 唯一标识符
    // ============================================================
    /**
     * ObjectID 绑定
     *
     * C++ 类：miniray::ObjectID
     * Python 类：_miniray_core.ObjectID
     *
     * 用途：唯一标识对象、任务、函数等
     */
    py::class_<ObjectID>(m, "ObjectID")
        // 构造函数：创建一个空的（nil）ObjectID
        .def(py::init<>(),
             "Create a nil ObjectID")

        // 静态方法：生成随机 ObjectID
        // 在 Python 中调用：ObjectID.from_random()
        .def_static("from_random", &ObjectID::FromRandom,
                   "Generate a random ObjectID (128-bit UUID)")

        // 实例方法：转换为 16 进制字符串（32 字符）
        .def("to_hex", &ObjectID::ToHex,
             "Convert to hexadecimal string (32 characters)")

        // 实例方法：检查是否为空
        .def("is_nil", &ObjectID::IsNil,
             "Check if ObjectID is nil (all zeros)")

        // 相等性比较运算符
        // 让 Python 可以使用：id1 == id2
        .def("__eq__", &ObjectID::operator==)
        .def("__ne__", &ObjectID::operator!=)

        // Python repr() 函数的实现
        // 让 Python 可以使用：repr(obj_id) 或直接打印
        .def("__repr__", [](const ObjectID& id) {
            // 只显示前 8 个字符，避免输出过长
            return "ObjectID(" + id.ToHex().substr(0, 8) + "...)";
        })

        // Python hash() 函数的实现
        // 让 ObjectID 可以作为字典的键或放入集合
        .def("__hash__", [](const ObjectID& id) {
            return std::hash<ObjectID>()(id);
        });

    // ============================================================
    // ObjectRef - 对象引用（类似 Future）
    // ============================================================
    /**
     * ObjectRef 绑定
     *
     * C++ 类：miniray::ObjectRef
     * Python 类：_miniray_core.ObjectRef
     *
     * 用途：引用一个对象（可能还未计算完成）
     * 设计模式：Future/Promise
     */
    py::class_<ObjectRef>(m, "ObjectRef")
        // 构造函数1：创建新的 ObjectRef（自动生成随机 ObjectID）
        .def(py::init<>(),
             "Create a new ObjectRef with random ObjectID")

        // 构造函数2：从现有 ObjectID 创建 ObjectRef
        // py::arg("object_id") 为参数命名，支持关键字参数调用
        .def(py::init<const ObjectID&>(),
             "Create ObjectRef from existing ObjectID",
             py::arg("object_id"))

        // 获取底层的 ObjectID
        // return_value_policy::reference_internal 表示返回的引用
        // 生命周期与 ObjectRef 对象绑定，避免悬空引用
        .def("get_object_id", &ObjectRef::GetObjectID,
             py::return_value_policy::reference_internal,
             "Get the underlying ObjectID")

        // 相等性比较
        .def("__eq__", &ObjectRef::operator==)
        .def("__ne__", &ObjectRef::operator!=)

        // Python 字符串表示
        .def("__repr__", &ObjectRef::ToString)

        // Hash 支持（可作为字典键）
        .def("__hash__", [](const ObjectRef& ref) {
            return std::hash<ObjectRef>()(ref);
        });

    // ============================================================
    // Buffer - 内存缓冲区
    // ============================================================
    /**
     * Buffer 绑定
     *
     * C++ 类：miniray::Buffer
     * Python 类：_miniray_core.Buffer
     *
     * 用途：封装对象存储中的数据缓冲区
     * 注意：使用 std::shared_ptr<Buffer> 管理生命周期
     */
    py::class_<Buffer, std::shared_ptr<Buffer>>(m, "Buffer")
        // 获取缓冲区大小
        .def("size", &Buffer::Size,
             "Get buffer size in bytes")

        // 转换为 Python bytes 对象
        // 使用 lambda 进行类型转换：Buffer -> Python bytes
        .def("to_bytes", [](const Buffer& buffer) {
            // reinterpret_cast：将 uint8_t* 转换为 const char*
            // py::bytes：创建 Python bytes 对象
            return py::bytes(reinterpret_cast<const char*>(buffer.Data()),
                           buffer.Size());
        }, "Convert buffer to Python bytes object");

    // ============================================================
    // ObjectStore - 对象存储（核心组件）
    // ============================================================
    /**
     * ObjectStore 绑定
     *
     * C++ 类：miniray::ObjectStore
     * Python 类：_miniray_core.ObjectStore
     *
     * 用途：线程安全的对象存储，支持 put/get/delete 操作
     */
    py::class_<ObjectStore>(m, "ObjectStore")
        // 构造函数：创建空的 ObjectStore
        .def(py::init<>(),
             "Create a new ObjectStore instance")

        /**
         * put 方法：存储对象
         *
         * 类型转换流程：
         *   Python bytes -> C++ std::string -> C++ std::vector<uint8_t>
         *
         * 为什么需要 lambda：
         *   - C++ 的 Put() 接受 std::vector<uint8_t>
         *   - Python 传入的是 py::bytes
         *   - 需要中间转换层
         */
        .def("put", [](ObjectStore& store, py::bytes data) {
            // 步骤1：py::bytes 隐式转换为 std::string
            std::string str = data;

            // 步骤2：std::string 转换为 std::vector<uint8_t>
            // str.begin() 和 str.end() 是迭代器
            std::vector<uint8_t> vec(str.begin(), str.end());

            // 步骤3：调用 C++ 的 Put 方法，返回 ObjectRef
            return store.Put(vec);
        },
        py::arg("data"),
        "Store an object and return ObjectRef\n\n"
        "Args:\n"
        "    data (bytes): Object data to store\n\n"
        "Returns:\n"
        "    ObjectRef: Reference to the stored object")

        /**
         * get 方法：获取对象
         *
         * 类型转换流程：
         *   ObjectRef -> C++ Buffer -> Python bytes
         *
         * 为什么需要 lambda：
         *   - C++ 的 Get() 返回 std::shared_ptr<Buffer>
         *   - Python 需要的是 bytes
         *   - 需要解引用 Buffer 并转换
         */
        .def("get", [](ObjectStore& store, const ObjectRef& ref) {
            // 步骤1：调用 C++ 的 Get 方法，返回 shared_ptr<Buffer>
            auto buffer = store.Get(ref);

            // 步骤2：将 Buffer 数据转换为 Python bytes
            // buffer->Data() 返回 const uint8_t*
            // reinterpret_cast 转换为 const char*（bytes 需要）
            return py::bytes(reinterpret_cast<const char*>(buffer->Data()),
                           buffer->Size());
        },
        py::arg("object_ref"),
        "Get object data by ObjectRef\n\n"
        "Args:\n"
        "    object_ref (ObjectRef): Reference to the object\n\n"
        "Returns:\n"
        "    bytes: Object data\n\n"
        "Raises:\n"
        "    RuntimeError: If object does not exist")

        // delete 方法：删除对象
        // 直接绑定 C++ 方法，不需要类型转换
        .def("delete", &ObjectStore::Delete,
             py::arg("object_ref"),
             "Delete object by ObjectRef\n\n"
             "Args:\n"
             "    object_ref (ObjectRef): Reference to the object to delete")

        // contains 方法：检查对象是否存在
        .def("contains", &ObjectStore::Contains,
             py::arg("object_ref"),
             "Check if object exists in the store\n\n"
             "Args:\n"
             "    object_ref (ObjectRef): Reference to check\n\n"
             "Returns:\n"
             "    bool: True if object exists, False otherwise")

        // size 方法：获取对象数量
        .def("size", &ObjectStore::Size,
             "Get number of objects in store\n\n"
             "Returns:\n"
             "    int: Number of stored objects")

        // Python len() 函数支持
        // 让 Python 可以使用：len(store)
        .def("__len__", &ObjectStore::Size);

    // ============================================================
    // TaskSpec - 任务规格（Phase 2）
    // ============================================================
    /**
     * TaskSpec 绑定
     *
     * C++ 类：miniray::TaskSpec
     * Python 类：_miniray_core.TaskSpec
     *
     * 用途：描述一个任务的元数据（函数、参数等）
     */
    py::class_<TaskSpec>(m, "TaskSpec")
        // 构造函数
        .def(py::init<>(),
             "Create a new TaskSpec")

        // 可读写属性：任务 ID
        // def_readwrite 允许 Python 读写这个字段
        // Python 使用：task_spec.task_id = xxx
        .def_readwrite("task_id", &TaskSpec::task_id,
                      "Task unique identifier (ObjectID)")

        // 可读写属性：函数 ID
        .def_readwrite("function_id", &TaskSpec::function_id,
                      "Function unique identifier (ObjectID)")

        // 可读写属性：序列化的函数
        // std::vector<uint8_t> 自动转换为 Python list
        .def_readwrite("serialized_function", &TaskSpec::serialized_function,
                      "Serialized function data (list of bytes)")

        // 可读写属性：序列化的参数
        .def_readwrite("serialized_args", &TaskSpec::serialized_args,
                      "Serialized arguments data (list of bytes)");

    // ============================================================
    // Task - 任务对象（Phase 2）
    // ============================================================
    /**
     * Task 绑定
     *
     * C++ 类：miniray::Task
     * Python 类：_miniray_core.Task
     *
     * 用途：表示一个可执行的任务
     */
    py::class_<Task>(m, "Task")
        // 构造函数1：创建空任务
        .def(py::init<>(),
             "Create a new empty Task")

        // 构造函数2：从 TaskSpec 创建任务
        .def(py::init<const TaskSpec&>(),
             py::arg("task_spec"),
             "Create Task from TaskSpec")

        // 可读写属性：任务规格
        .def_readwrite("task_spec", &Task::task_spec,
                      "Task specification (TaskSpec)")

        // 可读写属性：返回值引用
        .def_readwrite("return_ref", &Task::return_ref,
                      "Reference to task return value (ObjectRef)");

    // ============================================================
    // 模块元数据
    // ============================================================

    // 版本信息
    // Python 使用：_miniray_core.__version__
    m.attr("__version__") = "0.1.0";
}

/**
 * 编译说明：
 *
 * 这个文件由 CMake + pybind11 编译，生成 Python 扩展模块。
 *
 * 编译命令（由 CMakeLists.txt 自动执行）：
 *   c++ -O3 -shared -std=c++17 -fPIC \
 *       -I/path/to/pybind11/include \
 *       -I/path/to/python/include \
 *       python_bindings.cpp -o _miniray_core.so
 *
 * 编译产物：
 *   - macOS: _miniray_core.so
 *   - Linux: _miniray_core.so
 *   - Windows: _miniray_core.pyd
 */

/**
 * 使用示例：
 *
 * Python 代码：
 *
 *   import _miniray_core as core
 *
 *   # 创建 ObjectStore
 *   store = core.ObjectStore()
 *
 *   # 存储数据
 *   data = b"Hello, Mini-Ray!"
 *   ref = store.put(data)
 *
 *   # 获取数据
 *   retrieved = store.get(ref)
 *   assert retrieved == data
 *
 *   # 检查存在
 *   assert store.contains(ref)
 *
 *   # 删除数据
 *   store.delete(ref)
 */

/**
 * 常见问题：
 *
 * Q1: 为什么 put/get 需要 lambda？
 * A: 因为 Python bytes 和 C++ std::vector<uint8_t> 类型不同，
 *    需要显式转换。pybind11 不会自动转换 bytes ↔ vector<uint8_t>。
 *
 * Q2: 什么是 return_value_policy？
 * A: 控制返回值的生命周期管理：
 *    - reference_internal: 返回引用，生命周期与对象绑定
 *    - copy: 返回副本
 *    - take_ownership: 转移所有权
 *
 * Q3: def_readwrite 和 def_property 的区别？
 * A: - def_readwrite: 直接暴露 C++ 成员变量
 *    - def_property: 使用 getter/setter 函数（更灵活）
 *
 * Q4: 为什么 Buffer 使用 std::shared_ptr？
 * A: 因为 Buffer 可能被多个地方引用，shared_ptr 确保正确的
 *    生命周期管理，避免内存泄漏或悬空指针。
 */

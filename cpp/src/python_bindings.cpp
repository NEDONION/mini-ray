#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/operators.h>

#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include "miniray/common/task.h"
#include "miniray/object_store/object_store.h"

namespace py = pybind11;
using namespace miniray;

PYBIND11_MODULE(_miniray_core, m) {
    m.doc() = "Mini-Ray C++ Core Module";

    // ==================== ObjectID ====================
    py::class_<ObjectID>(m, "ObjectID")
        .def(py::init<>(), "Create a nil ObjectID")
        .def_static("from_random", &ObjectID::FromRandom,
                   "Generate a random ObjectID")
        .def("to_hex", &ObjectID::ToHex,
             "Convert to hexadecimal string")
        .def("is_nil", &ObjectID::IsNil,
             "Check if ObjectID is nil")
        .def("__eq__", &ObjectID::operator==)
        .def("__ne__", &ObjectID::operator!=)
        .def("__repr__", [](const ObjectID& id) {
            return "ObjectID(" + id.ToHex().substr(0, 8) + "...)";
        })
        .def("__hash__", [](const ObjectID& id) {
            return std::hash<ObjectID>()(id);
        });

    // ==================== ObjectRef ====================
    py::class_<ObjectRef>(m, "ObjectRef")
        .def(py::init<>(), "Create a new ObjectRef with random ObjectID")
        .def(py::init<const ObjectID&>(), "Create ObjectRef from ObjectID",
             py::arg("object_id"))
        .def("get_object_id", &ObjectRef::GetObjectID,
             py::return_value_policy::reference_internal,
             "Get the underlying ObjectID")
        .def("__eq__", &ObjectRef::operator==)
        .def("__ne__", &ObjectRef::operator!=)
        .def("__repr__", &ObjectRef::ToString)
        .def("__hash__", [](const ObjectRef& ref) {
            return std::hash<ObjectRef>()(ref);
        });

    // ==================== Buffer ====================
    py::class_<Buffer, std::shared_ptr<Buffer>>(m, "Buffer")
        .def("size", &Buffer::Size, "Get buffer size")
        .def("to_bytes", [](const Buffer& buffer) {
            return py::bytes(reinterpret_cast<const char*>(buffer.Data()),
                           buffer.Size());
        }, "Convert to Python bytes");

    // ==================== ObjectStore ====================
    py::class_<ObjectStore>(m, "ObjectStore")
        .def(py::init<>(), "Create a new ObjectStore")
        .def("put", [](ObjectStore& store, py::bytes data) {
            // 将 Python bytes 转换为 std::vector<uint8_t>
            std::string str = data;
            std::vector<uint8_t> vec(str.begin(), str.end());
            return store.Put(vec);
        }, py::arg("data"),
           "Store an object and return ObjectRef")
        .def("get", [](ObjectStore& store, const ObjectRef& ref) {
            auto buffer = store.Get(ref);
            // 将 Buffer 转换为 Python bytes
            return py::bytes(reinterpret_cast<const char*>(buffer->Data()),
                           buffer->Size());
        }, py::arg("object_ref"),
           "Get object data by ObjectRef")
        .def("delete", &ObjectStore::Delete, py::arg("object_ref"),
             "Delete object by ObjectRef")
        .def("contains", &ObjectStore::Contains, py::arg("object_ref"),
             "Check if object exists")
        .def("size", &ObjectStore::Size,
             "Get number of objects in store")
        .def("__len__", &ObjectStore::Size);

    // ==================== TaskSpec ====================
    py::class_<TaskSpec>(m, "TaskSpec")
        .def(py::init<>(), "Create a new TaskSpec")
        .def_readwrite("task_id", &TaskSpec::task_id)
        .def_readwrite("function_id", &TaskSpec::function_id)
        .def_readwrite("serialized_function", &TaskSpec::serialized_function)
        .def_readwrite("serialized_args", &TaskSpec::serialized_args);

    // ==================== Task ====================
    py::class_<Task>(m, "Task")
        .def(py::init<>(), "Create a new Task")
        .def(py::init<const TaskSpec&>(), py::arg("task_spec"))
        .def_readwrite("task_spec", &Task::task_spec)
        .def_readwrite("return_ref", &Task::return_ref);

    // 版本信息
    m.attr("__version__") = "0.1.0";
}

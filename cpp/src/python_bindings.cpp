/**
 * python_bindings.cpp - Python/C++ 绑定层
 *
 * (保留原注释...)
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/operators.h>
#include <pybind11/stl_bind.h> // 用于绑定 std::vector 等容器

#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include "miniray/common/task.h"
#include "miniray/common/buffer.h"
#include "miniray/core_worker/core_worker.h"
#include "miniray/object_store/object_store.h"
#include "miniray/raylet/scheduler.h"

namespace py = pybind11;
using namespace miniray;

PYBIND11_MODULE(_miniray_core, m) {
    m.doc() = "Mini-Ray C++ Core Module";

    /**
     * 绑定 ObjectID
     */
    py::class_<ObjectID>(m, "ObjectID")
        .def(py::init<>())
        .def_static("from_random", &ObjectID::FromRandom)
        .def_static("from_hex", &ObjectID::FromHex, py::arg("hex_string"))
        .def("to_hex", &ObjectID::ToHex)
        .def("is_nil", &ObjectID::IsNil)
        .def("__eq__", &ObjectID::operator==)
        .def("__ne__", &ObjectID::operator!=)
        .def("__repr__", [](const ObjectID& id) {
            return "ObjectID(" + id.ToHex().substr(0, 8) + "...)";
        })
        .def("__hash__", [](const ObjectID& id) {
            return std::hash<ObjectID>()(id);
        });

    /**
     * 绑定 ObjectRef
     */
    py::class_<ObjectRef>(m, "ObjectRef")
        .def(py::init<>())
        .def(py::init<const ObjectID&>(), py::arg("object_id"))
        .def_static("from_hex", [](const std::string& hex_string) {
            return ObjectRef(ObjectID::FromHex(hex_string));
        }, py::arg("hex_string"))
        .def("id", &ObjectRef::ID)
        .def("to_hex", &ObjectRef::ToHex)
        .def("__eq__", &ObjectRef::operator==)
        .def("__ne__", &ObjectRef::operator!=)
        .def("__repr__", [](const ObjectRef& ref) {
            return "ObjectRef(" + ref.ToHex().substr(0, 8) + "...)";
        })
        .def("__hash__", [](const ObjectRef& ref) {
            return std::hash<ObjectRef>()(ref);
        });

    /**
     * 绑定 Buffer
     * 注意：Buffer 被设计为数据的 C++ 容器，持有其所有权。
     */
    py::class_<Buffer, std::shared_ptr<Buffer>>(m, "Buffer")
        // 绑定 data 方法：返回 Python bytes，这里必须拷贝
        .def("data", [](const Buffer& buffer) {
            return py::bytes(reinterpret_cast<const char*>(buffer.Data()),
                             buffer.Size());
        })
        // 也可以考虑返回 memoryview (py::memoryview::from_buffer) 来实现零拷贝视图
        .def("size", &Buffer::Size)
        .def("__len__", &Buffer::Size)
        .def("__repr__", [](const Buffer& buffer) {
            return "Buffer(size=" + std::to_string(buffer.Size()) + ")";
        });

    /**
     * 绑定 Task
     */
    py::class_<Task>(m, "Task")
        .def(py::init<>())
        .def_readwrite("return_ref", &Task::return_ref)
        .def_readwrite("serialized_function", &Task::serialized_function)
        .def_readwrite("serialized_args", &Task::serialized_args)
        .def("__repr__", [](const Task& task) {
            return "Task(return_ref=" + task.return_ref.ToHex().substr(0, 8) + "...)";
        });

    /**
     * 绑定 ObjectStore（共享内存版本）
     */
    py::class_<object_store::ObjectStore, std::shared_ptr<object_store::ObjectStore>>(m, "ObjectStore")
        .def(py::init<bool>(), py::arg("create") = true)

        // 优化 Put：使用更高效的 lambda 转换 py::bytes 到 std::vector<uint8_t>
        .def("put", [](object_store::ObjectStore& store, py::bytes data) {
            // py::bytes 隐含地包含其大小和原始指针
            std::string_view sv = data;
            const uint8_t* ptr = reinterpret_cast<const uint8_t*>(sv.data());
            std::vector<uint8_t> vec(ptr, ptr + sv.size());
            return store.Put(vec);
        }, py::arg("data"))

        // 优化 Put With Ref
        .def("put_with_ref", [](object_store::ObjectStore& store, py::bytes data, const ObjectRef& ref) {
            std::string_view sv = data;
            const uint8_t* ptr = reinterpret_cast<const uint8_t*>(sv.data());
            std::vector<uint8_t> vec(ptr, ptr + sv.size());
            return store.Put(ref, vec);
        }, py::arg("data"), py::arg("ref"))

        // 优化 Get：直接返回 C++ Buffer 对象，避免二次拷贝！
        // Python 侧现在得到的是一个 <_miniray_core.Buffer object>，
        // 必须调用其 .data() 方法才能拿到 Python bytes。
        .def("get", &object_store::ObjectStore::Get, py::arg("object_ref"))

        .def("contains", &object_store::ObjectStore::Contains, py::arg("object_ref"))
        .def("remove", &object_store::ObjectStore::Delete, py::arg("object_ref"))
        .def("delete", &object_store::ObjectStore::Delete, py::arg("object_ref"))
        .def("size", &object_store::ObjectStore::Size)
        .def("__repr__", [](const object_store::ObjectStore& store) {
            return "ObjectStore(size=" + std::to_string(store.Size()) + ")";
        });

    /**
     * 绑定 Scheduler（共享内存版本）
     */
    py::class_<raylet::Scheduler, std::shared_ptr<raylet::Scheduler>>(m, "Scheduler")
        .def(py::init<bool>(), py::arg("create") = true)
        .def("submit_task", &raylet::Scheduler::SubmitTask, py::arg("task"))
        // 关键修改：按值返回 Task，或 None
        .def("get_next_task", [](raylet::Scheduler& sched) -> py::object {
            auto task_ptr = sched.GetNextTask();
            if (!task_ptr) {
                return py::none();
            }
            return py::cast(*task_ptr);  // 拷贝一份 Task（包含 vector 字段）
        })
        .def("register_worker", &raylet::Scheduler::RegisterWorker,
             py::arg("worker_id"))
        .def("unregister_worker", &raylet::Scheduler::UnregisterWorker,
             py::arg("worker_id"))
        .def("mark_worker_busy", &raylet::Scheduler::MarkWorkerBusy,
             py::arg("worker_id"))
        .def("mark_worker_idle", &raylet::Scheduler::MarkWorkerIdle,
             py::arg("worker_id"))
        .def("get_pending_task_count",
             &raylet::Scheduler::GetPendingTaskCount)
        .def("get_idle_worker_count",
             &raylet::Scheduler::GetIdleWorkerCount)
        .def("has_idle_worker", &raylet::Scheduler::HasIdleWorker)
        .def("__repr__", [](const raylet::Scheduler& sched) {
            return "Scheduler(pending=" +
                   std::to_string(sched.GetPendingTaskCount()) +
                   ", idle_workers=" +
                   std::to_string(sched.GetIdleWorkerCount()) + ")";
        });

    /**
     * 绑定 CoreWorker
     */
    py::class_<core_worker::CoreWorker>(m, "CoreWorker")
        .def(py::init<std::shared_ptr<raylet::Scheduler>,
                      std::shared_ptr<object_store::ObjectStore>,
                      int>(),
             py::arg("scheduler"),
             py::arg("object_store"),
             py::arg("worker_id"))
        .def("submit_task", &core_worker::CoreWorker::SubmitTask,
             py::arg("task"))
        // 关键修改：按值返回 Task，或 None
        .def("get_next_task", [](core_worker::CoreWorker& worker) -> py::object {
            auto task_ptr = worker.GetNextTask();
            if (!task_ptr) {
                return py::none();
            }
            return py::cast(*task_ptr);
        })
        .def("put_object", [](core_worker::CoreWorker& worker,
                              const ObjectRef& object_ref,
                              py::bytes data) {
            // 优化 CoreWorker::PutObject 的数据转换
            std::string_view sv = data;
            const uint8_t* ptr = reinterpret_cast<const uint8_t*>(sv.data());
            std::vector<uint8_t> vec(ptr, ptr + sv.size());
            worker.PutObject(object_ref, vec);
        }, py::arg("object_ref"), py::arg("data"))

        // 优化 CoreWorker::GetObject：直接返回 C++ Buffer
        .def("get_object", &core_worker::CoreWorker::GetObject, py::arg("object_ref"))

        .def("get_worker_id", &core_worker::CoreWorker::GetWorkerID)
        .def("mark_worker_busy", &core_worker::CoreWorker::MarkWorkerBusy)
        .def("mark_worker_idle", &core_worker::CoreWorker::MarkWorkerIdle)
        .def("__repr__", [](const core_worker::CoreWorker& worker) {
            return "CoreWorker(id=" + std::to_string(worker.GetWorkerID()) +
                   ")";
        });

    // 添加共享内存清理函数
    m.def("cleanup_shared_memory", []() {
        object_store::ObjectStore::Cleanup();
        raylet::Scheduler::Cleanup();
    }, "Clean up shared memory segments");
}
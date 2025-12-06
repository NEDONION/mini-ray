/**
 * python_bindings.cpp - Python/C++ 绑定层
 *
 * ============================================================
 * pybind11 语法和最佳实践
 * ============================================================
 *
 * 1. PYBIND11_MODULE 宏
 *    定义 Python 模块的入口
 *    模块名必须与编译产物名称一致
 *
 * 2. py::class_<CppType> 绑定类
 *    将 C++ 类暴露为 Python 类
 *    可选第二个模板参数指定持有者类型（如 shared_ptr）
 *
 * 3. .def() 绑定方法
 *    第一个参数：Python 方法名
 *    第二个参数：C++ 方法指针或 lambda
 *    可选：py::arg() 指定参数名，支持命名参数调用
 *
 * 4. lambda 表达式用于类型转换
 *    语法：[捕获列表](参数) { 函数体 }
 *    用途：Python 类型 ↔ C++ 类型的转换
 *    最佳实践：保持 lambda 简短，复杂逻辑提取为独立函数
 *
 * 5. reinterpret_cast 类型转换
 *    强制类型转换，不做任何检查
 *    用于：uint8_t* ↔ char* 等二进制数据转换
 *    最佳实践：仅在确保类型兼容时使用
 *
 * 6. py::bytes 和 std::vector<uint8_t> 互转
 *    Python bytes → C++: std::string → std::vector
 *    C++ → Python bytes: reinterpret_cast
 *
 * 7. __repr__, __hash__, __eq__ 等魔术方法
 *    让 C++ 对象在 Python 中表现更自然
 *    最佳实践：实现常用的魔术方法提升易用性
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/operators.h>

#include "miniray/common/id.h"
#include "miniray/common/object_ref.h"
#include "miniray/common/task.h"
#include "miniray/common/buffer.h"
#include "miniray/core_worker/core_worker.h"
#include "miniray/shared/shared_object_store.h"
#include "miniray/shared/shared_scheduler.h"

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
     */
    py::class_<Buffer, std::shared_ptr<Buffer>>(m, "Buffer")
        .def("data", [](const Buffer& buffer) {
            return py::bytes(reinterpret_cast<const char*>(buffer.Data()),
                             buffer.Size());
        })
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
    py::class_<shared::SharedObjectStore, std::shared_ptr<shared::SharedObjectStore>>(m, "ObjectStore")
        .def(py::init<bool>(), py::arg("create") = true)
        .def("put", [](shared::SharedObjectStore& store, py::bytes data) {
            std::string str = data;
            std::vector<uint8_t> vec(str.begin(), str.end());
            return store.Put(vec);
        }, py::arg("data"))
        .def("get", [](shared::SharedObjectStore& store, const ObjectRef& object_ref) {
            auto buffer = store.Get(object_ref);
            return py::bytes(reinterpret_cast<const char*>(buffer->Data()),
                             buffer->Size());
        }, py::arg("object_ref"))
        .def("contains", &shared::SharedObjectStore::Contains, py::arg("object_ref"))
        .def("remove", &shared::SharedObjectStore::Delete, py::arg("object_ref"))
        .def("delete", &shared::SharedObjectStore::Delete, py::arg("object_ref"))
        .def("size", &shared::SharedObjectStore::Size)
        .def("__repr__", [](const shared::SharedObjectStore& store) {
            return "ObjectStore(size=" + std::to_string(store.Size()) + ")";
        });

    /**
     * 绑定 Scheduler（共享内存版本）
     */
    py::class_<shared::SharedScheduler, std::shared_ptr<shared::SharedScheduler>>(m, "Scheduler")
        .def(py::init<bool>(), py::arg("create") = true)
        .def("submit_task", &shared::SharedScheduler::SubmitTask, py::arg("task"))
        // ⚠️ 关键修改：按值返回 Task，或 None
        .def("get_next_task", [](shared::SharedScheduler& sched) -> py::object {
            auto task_ptr = sched.GetNextTask();
            if (!task_ptr) {
                return py::none();
            }
            return py::cast(*task_ptr);  // 拷贝一份 Task（包含 vector 字段）
        })
        .def("register_worker", &shared::SharedScheduler::RegisterWorker,
             py::arg("worker_id"))
        .def("unregister_worker", &shared::SharedScheduler::UnregisterWorker,
             py::arg("worker_id"))
        .def("mark_worker_busy", &shared::SharedScheduler::MarkWorkerBusy,
             py::arg("worker_id"))
        .def("mark_worker_idle", &shared::SharedScheduler::MarkWorkerIdle,
             py::arg("worker_id"))
        .def("get_pending_task_count",
             &shared::SharedScheduler::GetPendingTaskCount)
        .def("get_idle_worker_count",
             &shared::SharedScheduler::GetIdleWorkerCount)
        .def("has_idle_worker", &shared::SharedScheduler::HasIdleWorker)
        .def("__repr__", [](const shared::SharedScheduler& sched) {
            return "Scheduler(pending=" +
                   std::to_string(sched.GetPendingTaskCount()) +
                   ", idle_workers=" +
                   std::to_string(sched.GetIdleWorkerCount()) + ")";
        });

    /**
     * 绑定 CoreWorker
     */
    py::class_<core_worker::CoreWorker>(m, "CoreWorker")
        .def(py::init<std::shared_ptr<shared::SharedScheduler>,
                      std::shared_ptr<shared::SharedObjectStore>,
                      int>(),
             py::arg("scheduler"),
             py::arg("object_store"),
             py::arg("worker_id"))
        .def("submit_task", &core_worker::CoreWorker::SubmitTask,
             py::arg("task"))
        // ⚠️ 关键修改：按值返回 Task，或 None
        .def("get_next_task", [](core_worker::CoreWorker& worker) -> py::object {
            auto task_ptr = worker.GetNextTask();
            if (!task_ptr) {
                return py::none();
            }
            return py::cast(*task_ptr);
        })
        .def("put_object", &core_worker::CoreWorker::PutObject,
             py::arg("object_ref"),
             py::arg("data"))
        .def("get_object", [](core_worker::CoreWorker& worker,
                              const ObjectRef& object_ref) {
            auto buffer = worker.GetObject(object_ref);
            return py::bytes(reinterpret_cast<const char*>(buffer->Data()),
                             buffer->Size());
        }, py::arg("object_ref"))
        .def("get_worker_id", &core_worker::CoreWorker::GetWorkerID)
        .def("mark_worker_busy", &core_worker::CoreWorker::MarkWorkerBusy)
        .def("mark_worker_idle", &core_worker::CoreWorker::MarkWorkerIdle)
        .def("__repr__", [](const core_worker::CoreWorker& worker) {
            return "CoreWorker(id=" + std::to_string(worker.GetWorkerID()) +
                   ")";
        });

    // 添加共享内存清理函数
    m.def("cleanup_shared_memory", []() {
        shared::SharedObjectStore::Cleanup();
        shared::SharedScheduler::Cleanup();
    }, "Clean up shared memory segments");
}

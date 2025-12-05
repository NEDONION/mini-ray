# Mini-Ray 测试目录

这个目录包含 Mini-Ray 项目的所有自动化测试。

## 📁 目录结构

```
tests/
├── conftest.py              # pytest 配置和共享 fixtures
├── test_object_store.py     # ObjectStore 功能测试
├── test_bindings.py         # pybind11 绑定测试
├── test_cpp_core.py         # 旧版测试（保留用于手动运行）
└── README.md                # 本文件
```

## 🎯 测试文件说明

### `conftest.py`
pytest 配置文件，提供：
- **共享 fixtures**：`core_module`, `object_store`, `sample_data` 等
- **路径设置**：自动添加 `python/miniray/` 到 sys.path
- **测试环境初始化**

### `test_object_store.py`
ObjectStore 的完整功能测试，包括：
- ✅ 基础功能：put, get, delete, contains
- ✅ Python 对象序列化：dict, list, 复杂对象
- ✅ 批量操作：批量存储、获取、删除
- ✅ 边界情况：空数据、大数据、不存在的 ref
- ✅ 集成测试：函数结果存储、多 worker 模拟、数据流水线

### `test_bindings.py`
pybind11 绑定的测试，验证：
- ✅ ObjectID：创建、唯一性、hex 转换、hash、相等性
- ✅ ObjectRef：创建、从 ObjectID 创建、hash、相等性
- ✅ TaskSpec：task_id, function_id, 序列化数据
- ✅ Task：return_ref, 从 TaskSpec 创建
- ✅ 类之间的交互：ObjectRef + ObjectStore, TaskSpec + Task

### `test_cpp_core.py`
旧版测试文件（保留用于手动运行），使用简单的函数而非 pytest 类。

## 🚀 运行测试

### 前置条件

1. **构建 C++ 扩展模块**：
   ```bash
   python3 setup.py build_ext --inplace
   ```

2. **安装 pytest**（如果还没安装）：
   ```bash
   pip install pytest pytest-cov
   ```

### 基本用法

```bash
# 运行所有测试
pytest tests/

# 运行所有测试（详细输出）
pytest tests/ -v

# 运行所有测试（显示打印信息）
pytest tests/ -s

# 运行特定测试文件
pytest tests/test_object_store.py

# 运行特定测试类
pytest tests/test_object_store.py::TestObjectStoreBasic

# 运行特定测试函数
pytest tests/test_object_store.py::TestObjectStoreBasic::test_put_and_get

# 运行名称包含特定关键字的测试
pytest tests/ -k "put"          # 运行所有包含 "put" 的测试
pytest tests/ -k "ObjectStore"  # 运行所有包含 "ObjectStore" 的测试
```

### 高级用法

```bash
# 显示测试覆盖率
pytest tests/ --cov=miniray --cov-report=html

# 只运行失败的测试
pytest tests/ --lf

# 运行直到第一个失败
pytest tests/ -x

# 并行运行测试（需要 pytest-xdist）
pip install pytest-xdist
pytest tests/ -n auto

# 生成 JUnit XML 报告（CI/CD 用）
pytest tests/ --junit-xml=test-results.xml
```

## 📊 测试组织

测试采用 **类组织** 方式，便于管理和扩展：

```python
# 示例：test_object_store.py

class TestObjectStoreBasic:
    """基础功能测试"""
    def test_put_and_get(self, object_store):
        ...

class TestObjectStorePythonObjects:
    """Python 对象序列化测试"""
    def test_store_python_dict(self, object_store):
        ...

class TestObjectStoreBatch:
    """批量操作测试"""
    def test_batch_put(self, object_store):
        ...
```

## 🔧 Fixtures 使用

### 内置 Fixtures

我们在 `conftest.py` 中提供了以下 fixtures：

1. **`core_module`**（session 级别）
   - 导入并返回 `_miniray_core` 模块
   - 整个测试会话只导入一次
   ```python
   def test_something(core_module):
       store = core_module.ObjectStore()
   ```

2. **`object_store`**（function 级别）
   - 为每个测试创建新的 ObjectStore 实例
   - 确保测试之间互不影响
   ```python
   def test_something(object_store):
       object_store.put(b"data")
   ```

3. **`sample_data`**
   - 提供各种类型的测试数据
   ```python
   def test_something(sample_data):
       assert sample_data['bytes'] == b"Hello, Mini-Ray!"
   ```

4. **`serialized_data`**
   - 提供 pickle 序列化后的测试数据
   ```python
   def test_something(object_store, serialized_data):
       ref = object_store.put(serialized_data['dict'])
   ```

### 创建自定义 Fixture

在 `conftest.py` 中添加：

```python
@pytest.fixture
def my_custom_fixture():
    # setup
    resource = create_resource()
    yield resource
    # teardown
    cleanup_resource(resource)
```

## 📝 编写新测试

### 测试命名规范

- 测试文件：`test_*.py` 或 `*_test.py`
- 测试类：`Test*`（首字母大写）
- 测试函数：`test_*`（小写，用下划线分隔）

### 测试模板

```python
"""
新功能测试
"""
import pytest


class TestNewFeature:
    """新功能的测试"""

    def test_basic_functionality(self, object_store):
        """测试基础功能"""
        # Arrange（准备）
        data = b"test data"

        # Act（执行）
        result = object_store.put(data)

        # Assert（断言）
        assert result is not None

    def test_edge_case(self, object_store):
        """测试边界情况"""
        # ...
```

### 最佳实践

1. **每个测试只测试一件事**
   ```python
   # 好 ✅
   def test_put_returns_ref(self, object_store):
       ref = object_store.put(b"data")
       assert ref is not None

   def test_put_increments_size(self, object_store):
       object_store.put(b"data")
       assert object_store.size() == 1

   # 不好 ❌
   def test_put(self, object_store):
       ref = object_store.put(b"data")
       assert ref is not None
       assert object_store.size() == 1
       assert object_store.contains(ref)
   ```

2. **使用描述性的测试名称**
   ```python
   # 好 ✅
   def test_delete_nonexistent_ref_does_not_raise_error(self, object_store):
       ...

   # 不好 ❌
   def test_delete(self, object_store):
       ...
   ```

3. **使用 fixtures 避免重复代码**
   ```python
   # 好 ✅
   @pytest.fixture
   def stored_ref(object_store):
       return object_store.put(b"data")

   def test_get(self, object_store, stored_ref):
       data = object_store.get(stored_ref)
       assert data == b"data"
   ```

4. **使用参数化测试减少重复**
   ```python
   @pytest.mark.parametrize("data", [
       b"",
       b"small",
       b"x" * 1000,
       b"x" * 1000000,
   ])
   def test_store_various_sizes(self, object_store, data):
       ref = object_store.put(data)
       retrieved = object_store.get(ref)
       assert retrieved == data
   ```

## 🐛 调试测试

### 查看详细输出

```bash
# 显示 print 语句
pytest tests/test_object_store.py -s

# 显示本地变量（失败时）
pytest tests/test_object_store.py -l

# 进入 pdb 调试器（失败时）
pytest tests/test_object_store.py --pdb

# 在测试开始时进入 pdb
pytest tests/test_object_store.py --trace
```

### 在测试中添加断点

```python
def test_something(object_store):
    data = b"test"
    ref = object_store.put(data)

    import pdb; pdb.set_trace()  # 在这里暂停

    retrieved = object_store.get(ref)
    assert retrieved == data
```

## ⚠️ 常见问题

### 1. ImportError: No module named '_miniray_core'

**原因**：C++ 扩展模块未构建或不在正确位置

**解决方案**：
```bash
# 重新构建
python3 setup.py build_ext --inplace

# 确认 .so 文件存在
ls python/miniray/_miniray_core*.so
```

### 2. pytest: command not found

**原因**：pytest 未安装

**解决方案**：
```bash
pip install pytest
```

### 3. 测试通过但 import 失败（IDE 中）

**原因**：IDE 的 Python 路径配置问题

**解决方案**：
- 在 PyCharm 中：将 `python/` 标记为 "Sources Root"
- 或使用命令行运行测试

## 📚 参考资料

- [pytest 官方文档](https://docs.pytest.org/)
- [pytest fixtures 指南](https://docs.pytest.org/en/stable/fixture.html)
- [pytest 参数化测试](https://docs.pytest.org/en/stable/parametrize.html)
- [Python unittest 文档](https://docs.python.org/3/library/unittest.html)

## 🎓 与验收测试的区别

| 特性 | 单元测试（tests/）| 验收测试（test_phase1.py）|
|------|------------------|--------------------------|
| 目的 | 验证每个组件是否正常工作 | 验证整个 Phase 的功能是否完整 |
| 粒度 | 细粒度（单个函数/方法） | 粗粒度（完整功能） |
| 运行方式 | `pytest tests/` | `python3 test_phase1.py` |
| 失败处理 | 继续运行其他测试 | 通常在第一个错误时停止 |
| 用途 | 开发过程中频繁运行 | 阶段性里程碑验证 |

## 📝 贡献指南

添加新测试时，请确保：

1. ✅ 测试文件名以 `test_` 开头
2. ✅ 测试类名以 `Test` 开头
3. ✅ 测试函数名以 `test_` 开头
4. ✅ 添加有意义的 docstring
5. ✅ 使用现有的 fixtures
6. ✅ 保持测试独立（不依赖其他测试）
7. ✅ 运行 `pytest tests/` 确保所有测试通过

---

Happy Testing! 🧪✨

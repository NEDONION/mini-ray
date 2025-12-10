# Mini-Ray Dashboard 前端界面

重新设计的现代前端界面，提供系统监控、训练任务管理和历史记录查看功能。

## 功能特性

### 1. 系统监控
- **CPU 使用率**: 实时显示 CPU 使用情况
- **内存使用率**: 监控内存占用情况
- **磁盘使用率**: 显示磁盘空间使用情况
- **GPU 信息**: (如果可用) 显示 GPU 使用情况和内存

### 2. 任务管理
- **当前训练任务**: 显示正在运行的训练任务，包括进度条
- **历史训练任务**: 查看已完成的训练任务
- **所有任务**: 统一查看所有类型的任务

### 3. 任务详情
- **点击任务卡片**: 查看详细的事件历史
- **配置信息**: 显示任务配置参数
- **结果信息**: 显示任务执行结果
- **时间戳**: 任务创建和更新时间

## 界面设计

### 响应式布局
- 适配桌面、平板和移动设备
- 使用 Tailwind CSS 进行现代化设计
- 直观的卡片式布局

### 导航标签
- **系统监控**: 查看系统资源使用情况
- **训练任务**: 专门的训练任务管理
- **所有任务**: 查看全部任务

### 可视化元素
- 进度条显示任务完成度
- 颜色编码的状态指示器
- 实时更新的仪表板

## API 接口

前端通过以下 API 接口获取数据：

```
GET /api/system-info     # 系统信息 (OS, CPU, 内存, GPU等)
GET /api/metrics        # 实时指标 (CPU%, 内存%, 磁盘%)
GET /api/tasks          # 所有任务列表
GET /api/training-jobs  # 训练任务列表
GET /api/stats          # 统计信息
```

## 使用方法

### 启动 Dashboard
```bash
# 方式1: 直接运行
python -m miniray.dashboard

# 方式2: 通过API
from miniray.dashboard import run_dashboard
run_dashboard(host='0.0.0.0', port=8266)
```

### 访问界面
- 打开浏览器访问: http://localhost:8266
- 实时查看系统状态和任务进度

### 任务跟踪
使用装饰器自动将任务注册到 Dashboard：

```python
from miniray import track_training_job

@track_training_job(name="My Training", description="模型训练")
def train_model():
    # 你的训练代码
    return {"accuracy": 0.95}

result = train_model()  # 自动在 Dashboard 中显示
```

## 技术栈

- **前端**: React + Tailwind CSS + Font Awesome
- **后端**: Flask API
- **数据**: 通过事件系统和持久化存储
- **实时更新**: 每5秒自动刷新数据

## 自定义

### 模板文件
- `templates/dashboard.html`: 主界面模板
- 集成了 React 组件和 Tailwind CSS

### API 扩展
可以通过扩展 `app.py` 中的路由来添加新的功能。

## 故障排除

1. **界面无法加载**: 确保 Flask 和相关依赖已安装
2. **数据不更新**: 检查后台任务是否正在运行
3. **GPU 信息缺失**: 系统可能不支持 GPU 监控

## 开发

前端使用了 Babel Standalone 来实时编译 React JSX，便于开发和部署。
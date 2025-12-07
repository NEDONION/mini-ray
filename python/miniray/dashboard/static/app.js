/**
 * Mini-Ray Dashboard 前端逻辑
 *
 * 使用原生 JavaScript + Fetch API
 * 定时轮询更新数据
 */

// 配置
const REFRESH_INTERVAL = 2000; // 2 秒刷新一次

// 状态
let isConnected = true;
let refreshTimer = null;

/**
 * 格式化时间戳
 */
function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${hours}:${minutes}:${seconds}`;
}

/**
 * 格式化持续时间
 */
function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) {
        return 'N/A';
    }
    if (seconds < 1) {
        return `${(seconds * 1000).toFixed(0)}ms`;
    }
    if (seconds < 60) {
        return `${seconds.toFixed(2)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m ${remainingSeconds}s`;
}

/**
 * 格式化运行时间
 */
function formatUptime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

/**
 * 截断字符串
 */
function truncate(str, maxLength = 30) {
    if (typeof str !== 'string') {
        str = JSON.stringify(str);
    }
    if (str.length <= maxLength) {
        return str;
    }
    return str.substring(0, maxLength) + '...';
}

/**
 * 获取状态对应的 CSS 类
 */
function getStatusClass(status) {
    const statusMap = {
        'COMPLETED': 'status-completed',
        'RUNNING': 'status-running',
        'FAILED': 'status-failed',
        'PENDING': 'status-pending',
        'IDLE': 'status-idle',
        'BUSY': 'status-busy',
        'OFFLINE': 'status-offline',
    };
    return statusMap[status] || 'status-pending';
}

/**
 * 更新连接状态
 */
function updateConnectionStatus(connected) {
    const statusBadge = document.getElementById('connection-status');
    const dot = statusBadge.querySelector('.dot');
    const text = statusBadge.querySelector('span:last-child');

    if (connected) {
        dot.className = 'dot dot-green';
        text.textContent = 'Connected';
        isConnected = true;
    } else {
        dot.className = 'dot dot-red';
        text.textContent = 'Disconnected';
        isConnected = false;
    }
}

/**
 * 更新统计卡片
 */
function updateStats(stats) {
    // 任务统计
    document.getElementById('total-tasks').textContent = stats.tasks.total;
    document.getElementById('completed-tasks').textContent = stats.tasks.completed;
    document.getElementById('running-tasks').textContent = stats.tasks.running;
    document.getElementById('avg-duration').textContent = formatDuration(stats.tasks.avg_duration);

    // Worker 统计
    document.getElementById('total-workers').textContent = `${stats.workers.active}/${stats.workers.total}`;

    // 系统指标
    document.getElementById('cpu-usage').textContent = stats.system.cpu_percent.toFixed(1) + '%';
    document.getElementById('memory-usage').textContent = stats.system.memory_percent.toFixed(1) + '%';

    // 运行时间
    document.getElementById('uptime').textContent = formatUptime(stats.uptime);
}

/**
 * 更新任务列表
 */
function updateTasks(data) {
    const tasksTable = document.getElementById('tasks-table');
    const tasksCount = document.getElementById('tasks-count');

    // 更新计数
    tasksCount.textContent = data.total;

    // 清空表格
    tasksTable.innerHTML = '';

    if (data.tasks.length === 0) {
        tasksTable.innerHTML = '<tr><td colspan="5" class="text-center">No tasks yet...</td></tr>';
        return;
    }

    // 添加任务行
    data.tasks.forEach(task => {
        const row = document.createElement('tr');

        // Task ID（截断）
        const taskIdCell = document.createElement('td');
        taskIdCell.textContent = task.task_id.substring(0, 8) + '...';
        taskIdCell.title = task.task_id;
        row.appendChild(taskIdCell);

        // Status
        const statusCell = document.createElement('td');
        const statusBadge = document.createElement('span');
        statusBadge.className = `status-badge-table ${getStatusClass(task.status)}`;
        statusBadge.textContent = task.status;
        statusCell.appendChild(statusBadge);
        row.appendChild(statusCell);

        // Config
        const configCell = document.createElement('td');
        configCell.textContent = truncate(JSON.stringify(task.config), 40);
        configCell.title = JSON.stringify(task.config, null, 2);
        row.appendChild(configCell);

        // Duration
        const durationCell = document.createElement('td');
        durationCell.textContent = formatDuration(task.duration);
        row.appendChild(durationCell);

        // Time
        const timeCell = document.createElement('td');
        timeCell.textContent = formatTimestamp(task.timestamp);
        row.appendChild(timeCell);

        tasksTable.appendChild(row);
    });
}

/**
 * 更新 Worker 列表
 */
function updateWorkers(data) {
    const workersTable = document.getElementById('workers-table');
    const workersCount = document.getElementById('workers-count');

    // 更新计数
    workersCount.textContent = data.total;

    // 清空表格
    workersTable.innerHTML = '';

    if (data.workers.length === 0) {
        workersTable.innerHTML = '<tr><td colspan="3" class="text-center">No workers yet...</td></tr>';
        return;
    }

    // 添加 Worker 行
    data.workers.forEach(worker => {
        const row = document.createElement('tr');

        // Worker ID
        const idCell = document.createElement('td');
        idCell.textContent = `Worker ${worker.worker_id}`;
        row.appendChild(idCell);

        // Status
        const statusCell = document.createElement('td');
        const statusBadge = document.createElement('span');
        statusBadge.className = `status-badge-table ${getStatusClass(worker.status)}`;
        statusBadge.textContent = worker.status;
        statusCell.appendChild(statusBadge);
        row.appendChild(statusCell);

        // Last Updated
        const timeCell = document.createElement('td');
        timeCell.textContent = formatTimestamp(worker.last_updated);
        row.appendChild(timeCell);

        workersTable.appendChild(row);
    });
}

/**
 * 获取统计数据
 */
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) {
            throw new Error('Failed to fetch stats');
        }
        const stats = await response.json();
        updateStats(stats);
        updateConnectionStatus(true);
    } catch (error) {
        console.error('Error fetching stats:', error);
        updateConnectionStatus(false);
    }
}

/**
 * 获取任务列表
 */
async function fetchTasks() {
    try {
        const response = await fetch('/api/tasks');
        if (!response.ok) {
            throw new Error('Failed to fetch tasks');
        }
        const data = await response.json();
        updateTasks(data);
    } catch (error) {
        console.error('Error fetching tasks:', error);
    }
}

/**
 * 获取 Worker 列表
 */
async function fetchWorkers() {
    try {
        const response = await fetch('/api/workers');
        if (!response.ok) {
            throw new Error('Failed to fetch workers');
        }
        const data = await response.json();
        updateWorkers(data);
    } catch (error) {
        console.error('Error fetching workers:', error);
    }
}

/**
 * 刷新所有数据
 */
async function refreshAll() {
    await Promise.all([
        fetchStats(),
        fetchTasks(),
        fetchWorkers()
    ]);
}

/**
 * 启动自动刷新
 */
function startAutoRefresh() {
    // 立即刷新一次
    refreshAll();

    // 设置定时刷新
    refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);
}

/**
 * 停止自动刷新
 */
function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

/**
 * 页面加载完成后启动
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Mini-Ray Dashboard initialized');
    startAutoRefresh();
});

/**
 * 页面卸载前停止刷新
 */
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});

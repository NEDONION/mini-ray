"""
events.py - Mini-Ray 事件系统

提供事件总线来处理任务状态通知，并持久化到共享存储
"""
import threading
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import os
import tempfile
import time
from datetime import datetime


class TaskEventType(Enum):
    """任务事件类型"""
    TASK_SUBMITTED = "task_submitted"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_PROGRESS = "task_progress"


@dataclass
class TaskEvent:
    """任务事件数据结构"""
    event_type: TaskEventType
    task_id: str
    data: Optional[Dict] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class SharedStorage:
    """共享存储系统 - 持久化任务信息"""
    
    def __init__(self, storage_dir=None):
        self.storage_dir = storage_dir or os.path.join(tempfile.gettempdir(), 'miniray_dashboard')
        os.makedirs(self.storage_dir, exist_ok=True)
    
    def save_task_info(self, task_id: str, info: Dict[str, Any]):
        """保存任务信息到共享存储"""
        task_file = os.path.join(self.storage_dir, f"task_{task_id}.json")
        info['updated_at'] = time.time()
        info['updated_at_str'] = datetime.fromtimestamp(info['updated_at']).isoformat()
        
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """从共享存储获取任务信息"""
        task_file = os.path.join(self.storage_dir, f"task_{task_id}.json")
        if os.path.exists(task_file):
            with open(task_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """获取所有任务信息"""
        tasks = []
        for filename in os.listdir(self.storage_dir):
            if filename.startswith('task_') and filename.endswith('.json'):
                task_id = filename[5:-5]  # 移除 'task_' 前缀和 '.json' 后缀
                task_info = self.get_task_info(task_id)
                if task_info:
                    tasks.append(task_info)
        return tasks
    
    def delete_task_info(self, task_id: str):
        """删除任务信息"""
        task_file = os.path.join(self.storage_dir, f"task_{task_id}.json")
        if os.path.exists(task_file):
            os.remove(task_file)


class EventBus:
    """事件总线 - 负责事件发布和订阅"""
    
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._handlers: Dict[TaskEventType, List[Callable]] = {}
            self._storage = SharedStorage()
            self._initialized = True

    def subscribe(self, event_type: TaskEventType, handler: Callable):
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: TaskEvent):
        """发布事件"""
        # 首先保存到持久化存储
        self._handle_persistence(event)
        
        # 然后通知所有订阅者
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Event handler error: {e}")
    
    def _handle_persistence(self, event: TaskEvent):
        """处理持久化逻辑"""
        # 获取现有任务信息或创建新的
        task_info = self._storage.get_task_info(event.task_id)
        if not task_info:
            task_info = {
                'task_id': event.task_id,
                'created_at': event.timestamp,
                'created_at_str': datetime.fromtimestamp(event.timestamp).isoformat(),
                'type': 'unknown',
                'status': 'PENDING',
                'history': []
            }
        
        # 更新状态
        if event.event_type == TaskEventType.TASK_SUBMITTED:
            task_info.update({
                'status': 'PENDING',
                'type': event.data.get('type', 'task') if event.data else 'task',
                'name': event.data.get('name', f'Task {event.task_id[:8]}') if event.data else f'Task {event.task_id[:8]}',
                'description': event.data.get('description', '') if event.data else '',
                'config': event.data.get('config', {}) if event.data else {}
            })
        elif event.event_type == TaskEventType.TASK_STARTED:
            task_info['status'] = 'RUNNING'
            if event.data:
                task_info.update(event.data)
        elif event.event_type == TaskEventType.TASK_COMPLETED:
            task_info['status'] = 'COMPLETED'
            if event.data:
                task_info.update(event.data)
        elif event.event_type == TaskEventType.TASK_FAILED:
            task_info['status'] = 'FAILED'
            if event.data:
                task_info.update(event.data)
        elif event.event_type == TaskEventType.TASK_PROGRESS:
            task_info['progress'] = event.data.get('progress', 0) if event.data else 0
            if event.data:
                task_info.update(event.data)
        
        # 添加到历史记录
        event_record = {
            'event_type': event.event_type.value,
            'timestamp': event.timestamp,
            'timestamp_str': datetime.fromtimestamp(event.timestamp).isoformat(),
            'data': event.data
        }
        task_info['history'].append(event_record)
        
        # 限制历史记录数量以避免文件过大
        if len(task_info['history']) > 50:
            task_info['history'] = task_info['history'][-50:]
        
        # 保存到持久化存储
        self._storage.save_task_info(event.task_id, task_info)
    
    def get_storage(self) -> SharedStorage:
        """获取共享存储实例"""
        return self._storage


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    return EventBus()


def get_shared_storage() -> SharedStorage:
    """获取共享存储实例"""
    return EventBus().get_storage()
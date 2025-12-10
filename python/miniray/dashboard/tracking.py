"""
训练任务跟踪装饰器

提供 @track_training 装饰器来自动将训练任务注册到 Dashboard
"""
import functools
import time
import traceback
from typing import Any, Callable, Optional
from ..events import get_event_bus, TaskEventType, TaskEvent


def track_training(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "training"
):
    """
    装饰器：自动将函数的执行注册到 Dashboard 中进行跟踪

    Args:
        name: 任务名称，如果为 None，则使用函数名
        description: 任务描述
        category: 任务类别（training, inference, tuning 等）
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 生成任务 ID
            import uuid
            job_id = f"{category}_{str(uuid.uuid4())[:8]}"
            job_name = name or func.__name__

            # 获取参数信息（限制长度以防过大）
            params_str = f"args: {str(args)[:100]}, kwargs: {str(kwargs)[:100]}"

            # 获取事件总线实例
            event_bus = get_event_bus()

            # 记录任务开始
            start_time = time.time()
            try:
                # 发布任务提交事件
                submit_event = TaskEvent(
                    event_type=TaskEventType.TASK_SUBMITTED,
                    task_id=job_id,
                    data={
                        'type': category,
                        'name': job_name,
                        'status': 'PENDING',
                        'function': func.__name__,
                        'params': params_str,
                        'description': description or '',
                        'category': category
                    }
                )
                event_bus.publish(submit_event)

                print(f"[Dashboard] 任务已注册: {job_name} (ID: {job_id})")

                # 发布任务开始事件
                start_event = TaskEvent(
                    event_type=TaskEventType.TASK_STARTED,
                    task_id=job_id,
                    data={
                        'type': category,
                        'name': job_name,
                        'status': 'RUNNING',
                        'function': func.__name__,
                        'params': params_str,
                        'description': description or '',
                        'category': category,
                        'start_time': start_time
                    }
                )
                event_bus.publish(start_event)

                # 执行原始函数
                result = func(*args, **kwargs)

                # 记录任务完成
                duration = time.time() - start_time

                # 发布任务完成事件
                completion_event = TaskEvent(
                    event_type=TaskEventType.TASK_COMPLETED,
                    task_id=job_id,
                    data={
                        'type': category,
                        'name': job_name,
                        'status': 'COMPLETED',
                        'function': func.__name__,
                        'params': params_str,
                        'description': description or '',
                        'category': category,
                        'result': str(result)[:200] if result is not None else "None",
                        'duration': duration,
                        'end_time': time.time()
                    }
                )
                event_bus.publish(completion_event)

                print(f"[Dashboard] 任务完成: {job_name} (ID: {job_id})")
                return result

            except Exception as e:
                # 记录任务失败
                duration = time.time() - start_time
                error_msg = str(e)

                # 发布任务失败事件
                failure_event = TaskEvent(
                    event_type=TaskEventType.TASK_FAILED,
                    task_id=job_id,
                    data={
                        'type': category,
                        'name': job_name,
                        'status': 'FAILED',
                        'function': func.__name__,
                        'params': params_str,
                        'description': description or '',
                        'category': category,
                        'result': error_msg,
                        'duration': duration,
                        'error': error_msg,
                        'end_time': time.time()
                    }
                )
                event_bus.publish(failure_event)

                print(f"[Dashboard] 任务失败: {job_name} (ID: {job_id}) - {error_msg}")
                raise  # 重新抛出异常，保持原有行为

        return wrapper
    return decorator


# 便捷装饰器
def track_training_job(name: Optional[str] = None, description: Optional[str] = None):
    """专门用于训练任务的装饰器"""
    return track_training(name=name, description=description, category="training")


def track_inference_job(name: Optional[str] = None, description: Optional[str] = None):
    """专门用于推理任务的装饰器"""
    return track_training(name=name, description=description, category="inference")


def track_tuning_job(name: Optional[str] = None, description: Optional[str] = None):
    """专门用于调优任务的装饰器"""
    return track_training(name=name, description=description, category="tuning")
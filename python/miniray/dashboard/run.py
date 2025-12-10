#!/usr/bin/env python3
"""
启动 Mini-Ray Dashboard 服务器

使用方法:
    python -m miniray.dashboard.run
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from miniray.dashboard.app import run_dashboard


def main():
    """主函数"""
    print("🚀 启动 Mini-Ray Dashboard")
    print("=" * 50)
    print("系统监控 | 训练任务 | 任务历史")
    print("=" * 50)
    
    # 启动 Dashboard
    run_dashboard(host='0.0.0.0', port=8266, debug=False)


if __name__ == '__main__':
    main()
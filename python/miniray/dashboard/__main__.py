"""
运行 Mini-Ray Dashboard

使用方法:
    python -m miniray.dashboard
"""
from .app import run_dashboard

if __name__ == '__main__':
    run_dashboard(host='0.0.0.0', port=8266, debug=False)

#!/usr/bin/env python
"""
APScheduler 定时调度器（备用方案）
如果不想用 Windows 任务计划程序，可以直接运行此脚本常驻后台
用法: python scheduler.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from config import PREVIEW_HOUR, MORNING_HOUR
from daily_preview import main as preview_main
from morning_push import main as morning_main


def run_preview():
    print(f"[{datetime.now()}] [SCHED] Running preview push...")
    try:
        preview_main()
    except Exception as e:
        print(f"[{datetime.now()}] [ERROR] Preview push failed: {e}")


def run_morning():
    print(f"[{datetime.now()}] [SCHED] Running morning push...")
    try:
        morning_main()
    except Exception as e:
        print(f"[{datetime.now()}] [ERROR] Morning push failed: {e}")


if __name__ == "__main__":
    scheduler = BackgroundScheduler()

    # 每天固定时间触发
    scheduler.add_job(run_preview, "cron", hour=PREVIEW_HOUR, minute=0, id="preview")
    scheduler.add_job(run_morning, "cron", hour=MORNING_HOUR, minute=0, id="morning")

    scheduler.start()

    print(f"""
+============================================+
|  Scheduler Started                         |
|                                            |
|  Preview:  daily at {PREVIEW_HOUR:02d}:00                   |
|  Morning:  daily at {MORNING_HOUR:02d}:00                   |
|                                            |
|  Press Ctrl+C to stop                      |
+============================================+
    """)

    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")
        scheduler.shutdown()

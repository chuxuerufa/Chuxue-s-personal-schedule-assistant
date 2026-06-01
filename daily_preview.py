#!/usr/bin/env python
"""
每日预览推送脚本
由 Windows 任务计划程序在每天 22:00 调用
用法: python daily_preview.py
"""

import sys
import os
import uuid
from datetime import date, timedelta

# 确保能找到项目模块
sys.path.insert(0, os.path.dirname(__file__))

from config import FEISHU_WEBHOOK_URL, SITE_BASE_URL
from models import db, Plan, DailyTask, Confirmation, ConfirmStatus, PlanStatus
from feishu_push import send_card_message, build_preview_card
from app import app


def main():
    with app.app_context():
        plan = Plan.query.filter_by(status=PlanStatus.ACTIVE.value).first()
        if not plan:
            print("[预览推送] 没有活跃的备考计划，跳过")
            return

        tomorrow = date.today() + timedelta(days=1)

        # 获取明日任务
        tasks = (
            DailyTask.query
            .filter_by(plan_id=plan.id)
            .filter(DailyTask.task_date == tomorrow)
            .order_by(DailyTask.sort_order)
            .all()
        )

        if not tasks:
            # 没任务也推送提示
            tasks_list = []
            print(f"[预览推送] {tomorrow} 无任务安排")
        else:
            tasks_list = [t.to_dict() for t in tasks]

        # 生成确认 token
        token = str(uuid.uuid4())[:12]

        # 创建/更新确认记录
        conf = Confirmation.query.filter_by(confirm_date=tomorrow).first()
        if not conf:
            conf = Confirmation(
                confirm_date=tomorrow,
                token=token,
                status=ConfirmStatus.PENDING.value,
            )
            db.session.add(conf)
        else:
            conf.token = token
            conf.status = ConfirmStatus.PENDING.value

        conf.preview_msg_sent = True
        db.session.commit()

        # 构建确认/调整链接
        base = SITE_BASE_URL.rstrip("/")
        confirm_url = f"{base}/confirm/{token}?action=confirm"
        adjust_url = f"{base}/confirm/{token}?action=adjust"

        # 构建并发送飞书卡片
        card = build_preview_card(
            tasks=tasks_list,
            target_date=tomorrow,
            confirm_url=confirm_url,
            adjust_url=adjust_url,
        )

        success = send_card_message(FEISHU_WEBHOOK_URL, card)
        if success:
            print(f"[预览推送] [OK] 已推送 {tomorrow} 的预览（{len(tasks_list)} 项任务）")
        else:
            print(f"[预览推送] [FAIL] 推送失败")

        # 将之前的确认记录标记为过期
        yesterday = date.today()
        old_conf = Confirmation.query.filter_by(confirm_date=yesterday).first()
        if old_conf and old_conf.status == ConfirmStatus.PENDING.value:
            old_conf.status = ConfirmStatus.EXPIRED.value
            db.session.commit()


if __name__ == "__main__":
    main()

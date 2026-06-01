#!/usr/bin/env python
"""
早安推送脚本
由 Windows 任务计划程序在每天早上调用
用法: python morning_push.py
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from config import FEISHU_WEBHOOK_URL, SITE_BASE_URL
from models import db, Plan, DailyTask, Confirmation, ConfirmStatus, TaskStatus, PlanStatus
from feishu_push import send_card_message, build_morning_card
from app import app, _calc_streak


def main():
    with app.app_context():
        plan = Plan.query.filter_by(status=PlanStatus.ACTIVE.value).first()
        if not plan:
            print("[早安推送] 没有活跃的备考计划，跳过")
            return

        today = date.today()

        # 获取今日任务
        tasks = (
            DailyTask.query
            .filter_by(plan_id=plan.id)
            .filter(DailyTask.task_date == today)
            .order_by(DailyTask.sort_order)
            .all()
        )

        if not tasks:
            print(f"[早安推送] {today} 无任务安排，跳过推送")

            tasks_list = []
        else:
            tasks_list = [t.to_dict() for t in tasks]

        # 检查昨晚是否确认过
        confirmation = Confirmation.query.filter_by(confirm_date=today).first()
        was_confirmed = confirmation and confirmation.status in (
            ConfirmStatus.CONFIRMED.value,
            ConfirmStatus.ADJUSTED.value,
        )

        # 计算连续打卡天数
        streak = _calc_streak(plan.id)

        # 详情页链接
        detail_url = SITE_BASE_URL.rstrip("/") + "/"

        # 构建早安卡片
        card = build_morning_card(
            tasks=tasks_list,
            plan_name=plan.name,
            days_remaining=plan.to_dict()["days_remaining"],
            streak=streak,
            detail_url=detail_url,
        )

        # 如果未确认，添加提示
        if not was_confirmed and tasks_list:
            # 在卡片末尾添加提示
            card["elements"].append({
                "tag": "note",
                "elements": [{
                    "tag": "plain_text",
                    "content": "⚠️ 昨晚未确认计划，已按默认安排执行。你仍可在网页上随时调整。",
                }],
            })

        success = send_card_message(FEISHU_WEBHOOK_URL, card)
        if success:
            status = "已确认" if was_confirmed else "默认"
            print(f"[早安推送] [OK] 已推送 {today} 的计划（{status}，{len(tasks_list)} 项任务）")
        else:
            print(f"[早安推送] [FAIL] 推送失败")


if __name__ == "__main__":
    main()

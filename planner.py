"""AI 备考计划生成引擎"""

import json
import os
from datetime import datetime, date, timedelta
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from models import db, Plan, DailyTask, WeeklySummary, TaskStatus, TaskPriority

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _call_deepseek(system_prompt: str, user_message: str, user_ds_key: str = "") -> dict:
    """调用 DeepSeek API，返回解析后的 JSON"""
    _client = _get_client(user_ds_key)
    response = _client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=8192,
    )
    content = response.choices[0].message.content.strip()

    # 移除可能的 markdown 代码块标记
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return json.loads(content)


def _get_client(user_ds_key=""):
    """获取 AI 客户端，优先使用用户 Key"""
    key = user_ds_key or DEEPSEEK_API_KEY
    return OpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL)


def generate_initial_plan(
    exam_date_str: str,
    math_level: str,
    english_level: str,
    daily_hours: float,
    weak_subjects: str = "",
    user_ds_key: str = "",
    plan_name: str = "",
) -> Plan:
    """
    生成初始备考计划
    Args:
        exam_date_str: 考试日期 "YYYY-MM-DD"
        math_level: 高数水平描述（如"零基础"/"学过但不熟"/"有一定基础"）
        english_level: 英语水平描述
        daily_hours: 每天可用学习小时数
        weak_subjects: 薄弱环节描述
    """
    exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
    today = date.today()
    total_days = (exam_date - today).days

    system_prompt = _load_prompt("initial_plan.txt")

    user_message = f"""
考试日期：{exam_date_str}（距今天 {total_days} 天）
高数水平：{math_level}
英语水平：{english_level}
每天可用学习时间：{daily_hours} 小时
薄弱环节：{weak_subjects or "无特别说明"}

请从今天（{today.isoformat()}）开始规划，直到考试前一天。
每天总学习时长不超过 {daily_hours} 小时（即 {int(daily_hours * 60)} 分钟）。
"""

    plan_data = _call_deepseek(system_prompt, user_message, user_ds_key)

    # 创建 Plan
    plan = Plan(
        name=plan_name or plan_data.get("plan_name", "备考计划"),
        exam_date=exam_date,
    )
    db.session.add(plan)
    db.session.flush()  # 获取 plan.id

    # 解析阶段和周，创建 DailyTask
    task_offset = 0
    for phase in plan_data.get("phases", []):
        phase_start = datetime.strptime(phase["start_date"], "%Y-%m-%d").date()
        for week in phase.get("weeks", []):
            for task_data in week.get("tasks", []):
                task_date = phase_start + timedelta(days=task_data["day_offset"])
                if task_date >= exam_date:
                    continue  # 跳过考试当天及之后

                task = DailyTask(
                    plan_id=plan.id,
                    task_date=task_date,
                    subject=task_data.get("subject", "math"),
                    title=task_data["title"],
                    description=task_data.get("description", ""),
                    estimated_minutes=task_data.get("estimated_minutes", 60),
                    priority=task_data.get("priority", "medium"),
                    sort_order=task_data["day_offset"],
                )
                db.session.add(task)

    db.session.commit()
    return plan


def adjust_weekly_plan(
    plan_id: int,
    week_start: date,
    week_end: date,
    completion_rate: float,
    unfinished_tasks: list,
    daily_hours: float,
    user_ds_key: str = "",
) -> list[dict]:
    """
    根据本周完成情况，用 AI 调整下周计划
    返回调整后的任务列表（尚未写入数据库，供用户 review）
    """
    plan = db.session.get(Plan, plan_id)
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")

    # 获取下周原有任务
    next_monday = week_end + timedelta(days=1)
    next_sunday = next_monday + timedelta(days=6)
    existing_tasks = (
        DailyTask.query
        .filter(DailyTask.plan_id == plan_id)
        .filter(DailyTask.task_date >= next_monday)
        .filter(DailyTask.task_date <= next_sunday)
        .order_by(DailyTask.task_date, DailyTask.sort_order)
        .all()
    )

    system_prompt = _load_prompt("weekly_adjust.txt")

    user_message = json.dumps({
        "original_plan": [t.to_dict() for t in existing_tasks],
        "completion_rate": round(completion_rate, 2),
        "unfinished_tasks": unfinished_tasks,
        "daily_hours": daily_hours,
        "week_range": f"{next_monday.isoformat()} ~ {next_sunday.isoformat()}",
    }, ensure_ascii=False)

    adjusted = _call_deepseek(system_prompt, user_message, user_ds_key)

    # 创建/更新每周总结
    summary = WeeklySummary.query.filter_by(
        plan_id=plan_id, week_start=week_start
    ).first()
    if not summary:
        summary = WeeklySummary(
            plan_id=plan_id,
            week_start=week_start,
            week_end=week_end,
        )
    summary.completion_rate = completion_rate
    summary.ai_feedback = adjusted.get("adjustment_reason", "")
    summary.next_week_adjusted = True
    db.session.add(summary)

    # 标记旧任务为 AI 调整过（先不删，待用户确认）
    for t in existing_tasks:
        t.is_adjusted = True

    db.session.commit()

    return adjusted

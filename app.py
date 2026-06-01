"""Flask 主程序 —— 路由、API、页面渲染"""

import uuid
import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify

from config import (
    SECRET_KEY, DATABASE_URL, FLASK_HOST, FLASK_PORT,
    FEISHU_WEBHOOK_URL, SITE_BASE_URL, PREVIEW_HOUR, MORNING_HOUR,
)
from models import db, init_db, Plan, DailyTask, Confirmation, WeeklySummary
from models import TaskStatus, ConfirmStatus, TaskPriority, PlanStatus
from planner import generate_initial_plan, adjust_weekly_plan

# ─── App 初始化 ───────────────────────────────────────────

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# 确保数据库文件存在
with app.app_context():
    init_db(app)


# ─── 辅助函数 ─────────────────────────────────────────────

def _get_active_plan():
    """获取当前活跃的备考计划"""
    return Plan.query.filter_by(status=PlanStatus.ACTIVE.value).first()


def _get_today_tasks(plan_id=None):
    """获取今日任务列表"""
    if plan_id is None:
        plan = _get_active_plan()
        if not plan:
            return []
        plan_id = plan.id
    return (
        DailyTask.query
        .filter_by(plan_id=plan_id)
        .filter(DailyTask.task_date == date.today())
        .order_by(DailyTask.sort_order)
        .all()
    )


def _get_tasks_by_date(plan_id, target_date):
    """获取指定日期的任务"""
    return (
        DailyTask.query
        .filter_by(plan_id=plan_id)
        .filter(DailyTask.task_date == target_date)
        .order_by(DailyTask.sort_order)
        .all()
    )


def _calc_streak(plan_id):
    """计算连续打卡天数"""
    streak = 0
    check_date = date.today() - timedelta(days=1)
    while True:
        tasks = (
            DailyTask.query
            .filter_by(plan_id=plan_id)
            .filter(DailyTask.task_date == check_date)
            .all()
        )
        if not tasks:
            break
        completed = [t for t in tasks if t.status in (TaskStatus.COMPLETED.value, TaskStatus.PARTIAL.value)]
        if len(completed) == 0 and len(tasks) > 0:
            break
        streak += 1
        check_date -= timedelta(days=1)
    return streak


def _build_confirm_url(token, action="confirm"):
    """构建确认页面的完整 URL"""
    return f"{SITE_BASE_URL.rstrip('/')}/confirm/{token}?action={action}"


# ─── 页面路由 ─────────────────────────────────────────────

@app.route("/")
def index():
    """主页 —— 今日任务总览"""
    plan = _get_active_plan()
    if not plan:
        return redirect(url_for("plan_create"))

    tasks = _get_today_tasks(plan.id)
    streak = _calc_streak(plan.id)

    # 统计数据
    total = len(tasks)
    completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED.value])
    in_progress = len([t for t in tasks if t.status == TaskStatus.PARTIAL.value])

    return render_template(
        "index.html",
        plan=plan,
        tasks=tasks,
        streak=streak,
        total=total,
        completed=completed,
        in_progress=in_progress,
        today=date.today(),
    )


@app.route("/plan/create", methods=["GET", "POST"])
def plan_create():
    """创建备考计划"""
    existing = _get_active_plan()

    if request.method == "POST":
        # 如果已有活跃计划，先归档
        if existing:
            existing.status = PlanStatus.ARCHIVED.value
            db.session.commit()

        exam_date = request.form["exam_date"]
        math_level = request.form["math_level"]
        english_level = request.form["english_level"]
        daily_hours = float(request.form["daily_hours"])
        weak_subjects = request.form.get("weak_subjects", "")

        try:
            plan = generate_initial_plan(
                exam_date_str=exam_date,
                math_level=math_level,
                english_level=english_level,
                daily_hours=daily_hours,
                weak_subjects=weak_subjects,
            )
            return redirect(url_for("plan_view", plan_id=plan.id))
        except Exception as e:
            return render_template(
                "plan_create.html",
                error=f"AI 计划生成失败：{str(e)}",
                existing=existing,
            )

    return render_template("plan_create.html", existing=existing)


@app.route("/plan/<int:plan_id>")
def plan_view(plan_id):
    """查看完整备考计划"""
    plan = db.session.get(Plan, plan_id)
    if not plan:
        return "计划不存在", 404

    WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    # 按周分组，预计算所有显示字段
    all_tasks = sorted(plan.tasks, key=lambda t: (t.task_date, t.sort_order))
    all_dates = sorted(set(t.task_date for t in all_tasks))

    weeks = []
    if all_dates:
        week_start = all_dates[0]
        while week_start <= all_dates[-1]:
            week_end = week_start + timedelta(days=6)
            days = []
            # 遍历这周的每一天
            d = week_start
            while d <= week_end:
                days.append({
                    "date": d,
                    "iso": d.isoformat(),
                    "label": f"{d.month}/{d.day}",
                    "weekday": WEEKDAY_NAMES[d.weekday()],
                    "is_today": d == date.today(),
                })
                d += timedelta(days=1)

            weeks.append({
                "week_num": len(weeks) + 1,
                "start": week_start,
                "end": week_end,
                "start_label": f"{week_start.month}/{week_start.day}",
                "end_label": f"{week_end.month}/{week_end.day}",
                "is_current": week_start <= date.today() <= week_end,
                "days": days,
            })
            week_start = week_end + timedelta(days=1)

    # 构建 {日期: {math: [...], english: [...], rest: [...]}} 映射
    tasks_by_date = {}
    for t in all_tasks:
        key = t.task_date.isoformat()
        if key not in tasks_by_date:
            tasks_by_date[key] = {"math": [], "english": [], "rest": []}
        # 标准化 subject，防止 AI 返回非预期值
        subj = t.subject if t.subject in ("math", "english", "rest") else "rest"
        tasks_by_date[key][subj].append(t)

    return render_template(
        "plan_view.html",
        plan=plan,
        weeks=weeks,
        tasks_by_date=tasks_by_date,
        today=date.today(),
    )


@app.route("/confirm/<token>")
def confirm_page(token):
    """确认/调整明日计划页面"""
    confirmation = Confirmation.query.filter_by(token=token).first()
    if not confirmation:
        return "链接无效或已过期", 404

    plan = _get_active_plan()
    if not plan:
        return "没有活跃的备考计划", 400

    tasks = _get_tasks_by_date(plan.id, confirmation.confirm_date)
    action = request.args.get("action", "confirm")

    return render_template(
        "confirm.html",
        tasks=tasks,
        confirm_date=confirmation.confirm_date,
        token=token,
        action=action,
        plan=plan,
    )


@app.route("/progress")
def progress():
    """进度统计页面"""
    plan = _get_active_plan()
    if not plan:
        return redirect(url_for("plan_create"))

    # 按科目统计
    all_tasks = plan.tasks
    math_total = len([t for t in all_tasks if t.subject == "math"])
    eng_total = len([t for t in all_tasks if t.subject == "english"])
    math_done = len([t for t in all_tasks if t.subject == "math" and t.status == TaskStatus.COMPLETED.value])
    eng_done = len([t for t in all_tasks if t.subject == "english" and t.status == TaskStatus.COMPLETED.value])

    # 每日完成率
    dates_data = {}
    for t in sorted(all_tasks, key=lambda x: x.task_date):
        d = t.task_date.isoformat()
        if d not in dates_data:
            dates_data[d] = {"total": 0, "completed": 0}
        dates_data[d]["total"] += 1
        if t.status == TaskStatus.COMPLETED.value:
            dates_data[d]["completed"] += 1

    streak = _calc_streak(plan.id)

    return render_template(
        "progress.html",
        plan=plan,
        math_total=math_total,
        eng_total=eng_total,
        math_done=math_done,
        eng_done=eng_done,
        dates_data=dates_data,
        streak=streak,
    )


# ─── API 端点 ─────────────────────────────────────────────

@app.route("/api/task/<int:task_id>/check", methods=["POST"])
def api_check_task(task_id):
    """打卡/切换任务状态"""
    task = db.session.get(DailyTask, task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    data = request.get_json() or {}
    new_status = data.get("status", TaskStatus.COMPLETED.value)
    if new_status not in [s.value for s in TaskStatus]:
        return jsonify({"error": "无效状态"}), 400

    task.status = new_status
    db.session.commit()
    return jsonify({"ok": True, "task": task.to_dict()})


@app.route("/api/confirm", methods=["POST"])
def api_confirm():
    """提交确认"""
    data = request.get_json() or {}
    token = data.get("token")
    confirmation = Confirmation.query.filter_by(token=token).first()
    if not confirmation:
        return jsonify({"error": "无效 token"}), 404

    action = data.get("action", "confirmed")

    # 更新确认状态
    confirmation.status = action if action in ["confirmed", "adjusted"] else ConfirmStatus.CONFIRMED.value
    confirmation.confirmed_at = datetime.utcnow()

    # 更新任务状态为 confirmed
    plan = _get_active_plan()
    if plan:
        tasks = _get_tasks_by_date(plan.id, confirmation.confirm_date)
        for t in tasks:
            if t.status == TaskStatus.PENDING.value:
                t.status = TaskStatus.CONFIRMED.value

    db.session.commit()
    return jsonify({"ok": True, "status": confirmation.status})


@app.route("/api/confirm/adjust", methods=["POST"])
def api_adjust_tasks():
    """调整任务（增删改）"""
    data = request.get_json() or {}
    token = data.get("token")
    task_ids = data.get("task_ids", [])  # 保留的任务 ID 列表

    confirmation = Confirmation.query.filter_by(token=token).first()
    if not confirmation:
        return jsonify({"error": "无效 token"}), 404

    plan = _get_active_plan()
    if not plan:
        return jsonify({"error": "无活跃计划"}), 400

    # 删除不在保留列表中的任务
    existing = _get_tasks_by_date(plan.id, confirmation.confirm_date)
    for t in existing:
        if t.id not in task_ids:
            db.session.delete(t)
        else:
            t.status = TaskStatus.CONFIRMED.value

    # 添加新任务
    new_tasks = data.get("new_tasks", [])
    for nt in new_tasks:
        task = DailyTask(
            plan_id=plan.id,
            task_date=confirmation.confirm_date,
            subject=nt.get("subject", "math"),
            title=nt["title"],
            description=nt.get("description", ""),
            estimated_minutes=nt.get("estimated_minutes", 60),
            priority=nt.get("priority", "medium"),
            status=TaskStatus.CONFIRMED.value,
        )
        db.session.add(task)

    confirmation.status = ConfirmStatus.ADJUSTED.value
    confirmation.confirmed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/today")
def api_today():
    """获取今日任务 JSON（供推送脚本调用）"""
    plan = _get_active_plan()
    if not plan:
        return jsonify({"tasks": [], "plan": None})

    tasks = _get_today_tasks(plan.id)
    return jsonify({
        "plan": plan.to_dict(),
        "tasks": [t.to_dict() for t in tasks],
        "streak": _calc_streak(plan.id),
    })


@app.route("/api/tomorrow")
def api_tomorrow():
    """获取明日任务 JSON（供预览推送脚本调用）"""
    plan = _get_active_plan()
    if not plan:
        return jsonify({"tasks": [], "plan": None})

    tomorrow = date.today() + timedelta(days=1)
    tasks = _get_tasks_by_date(plan.id, tomorrow)
    return jsonify({
        "plan": plan.to_dict(),
        "tasks": [t.to_dict() for t in tasks],
        "date": tomorrow.isoformat(),
    })


@app.route("/api/plan/<int:plan_id>/adjust", methods=["POST"])
def api_adjust_weekly(plan_id):
    """触发 AI 周调整"""
    plan = db.session.get(Plan, plan_id)
    if not plan:
        return jsonify({"error": "计划不存在"}), 404

    data = request.get_json() or {}
    daily_hours = float(data.get("daily_hours", 4))

    # 计算本周范围
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # 统计本周完成率
    week_tasks = (
        DailyTask.query
        .filter_by(plan_id=plan_id)
        .filter(DailyTask.task_date >= week_start)
        .filter(DailyTask.task_date <= week_end)
        .all()
    )
    done = len([t for t in week_tasks if t.status == TaskStatus.COMPLETED.value])
    completion_rate = done / len(week_tasks) if week_tasks else 0

    # 未完成任务
    unfinished = [
        t.to_dict()
        for t in week_tasks
        if t.status not in (TaskStatus.COMPLETED.value, TaskStatus.SKIPPED.value)
    ]

    try:
        result = adjust_weekly_plan(
            plan_id=plan_id,
            week_start=week_start,
            week_end=week_end,
            completion_rate=completion_rate,
            unfinished_tasks=unfinished,
            daily_hours=daily_hours,
        )
        return jsonify({"ok": True, "adjustment": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── 启动入口 ─────────────────────────────────────────────

if __name__ == "__main__":
    print(f"""
+============================================+
|     Study Planner - AI Exam Prep v1.0      |
|                                            |
|  Local:  http://localhost:{FLASK_PORT}             |
|  Mobile: http://<your-ip>:{FLASK_PORT}             |
|                                            |
|  Scheduled pushes:                         |
|    Preview: {PREVIEW_HOUR:02d}:00 -> Feishu         |
|    Morning: {MORNING_HOUR:02d}:00 -> Feishu         |
+============================================+
    """)
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)

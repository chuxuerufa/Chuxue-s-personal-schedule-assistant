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


def _calc_heatmap(plan_id, days=42):
    """计算最近 N 天的打卡热力图数据"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    result = []

    d = start_date
    while d <= end_date:
        tasks = (
            DailyTask.query
            .filter_by(plan_id=plan_id)
            .filter(DailyTask.task_date == d)
            .all()
        )
        total = len(tasks)
        if total == 0:
            level = -1  # 无数据
        else:
            done = len([t for t in tasks if t.status == TaskStatus.COMPLETED.value])
            pct = done / total
            if pct == 0:
                level = 0
            elif pct < 0.4:
                level = 1
            elif pct < 0.7:
                level = 2
            elif pct < 1:
                level = 3
            else:
                level = 4
        result.append({
            "date": d.isoformat(),
            "label": f"{d.month}/{d.day}",
            "weekday": d.weekday(),
            "level": level,
            "total": total,
            "is_today": d == date.today(),
        })
        d += timedelta(days=1)

    return result


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

    # 完成百分比（用于 SVG 进度环）
    pct = int((completed + in_progress * 0.5) / total * 100) if total > 0 else 0
    # SVG 进度环：圆周长 = 2*PI*r ≈ 2*3.14159*44 ≈ 276.46
    ring_circumference = 276.46
    ring_offset = ring_circumference * (1 - pct / 100)

    # 热力图最近 42 天
    heatmap = _calc_heatmap(plan.id, 42)

    return render_template(
        "index.html",
        plan=plan,
        tasks=tasks,
        streak=streak,
        total=total,
        completed=completed,
        in_progress=in_progress,
        pct=pct,
        ring_offset=ring_offset,
        heatmap=heatmap,
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
    heatmap = _calc_heatmap(plan.id, 42)

    # 总体环形进度数据
    overall_total = math_total + eng_total
    overall_done = math_done + eng_done
    overall_pct = int(overall_done / overall_total * 100) if overall_total > 0 else 0
    ring_circumference_lg = 395.84  # 2*PI*63
    ring_offset_lg = ring_circumference_lg * (1 - overall_pct / 100)

    math_pct = int(math_done / math_total * 100) if math_total > 0 else 0
    eng_pct = int(eng_done / eng_total * 100) if eng_total > 0 else 0

    return render_template(
        "progress.html",
        plan=plan,
        math_total=math_total,
        eng_total=eng_total,
        math_done=math_done,
        eng_done=eng_done,
        math_pct=math_pct,
        eng_pct=eng_pct,
        overall_pct=overall_pct,
        ring_offset_lg=ring_offset_lg,
        dates_data=dates_data,
        heatmap=heatmap,
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


@app.route("/api/task", methods=["POST"])
def api_create_task():
    """手动创建今日新任务"""
    plan = _get_active_plan()
    if not plan:
        return jsonify({"error": "没有活跃的备考计划"}), 400

    data = request.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "任务标题不能为空"}), 400

    task = DailyTask(
        plan_id=plan.id,
        task_date=date.today(),
        subject=data.get("subject", "math"),
        title=title,
        description=data.get("description", ""),
        estimated_minutes=int(data.get("estimated_minutes", 60)),
        priority=data.get("priority", TaskPriority.MEDIUM.value),
        status=TaskStatus.CONFIRMED.value,
        is_adjusted=True,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"ok": True, "task": task.to_dict()}), 201


@app.route("/api/task/<int:task_id>", methods=["PUT"])
def api_update_task(task_id):
    """更新任务字段"""
    task = db.session.get(DailyTask, task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    data = request.get_json() or {}
    if "title" in data and data["title"].strip():
        task.title = data["title"].strip()
    if "subject" in data and data["subject"] in ("math", "english", "rest"):
        task.subject = data["subject"]
    if "estimated_minutes" in data:
        task.estimated_minutes = int(data["estimated_minutes"])
    if "priority" in data and data["priority"] in ("high", "medium", "low"):
        task.priority = data["priority"]
    if "description" in data:
        task.description = data["description"]

    task.is_adjusted = True
    db.session.commit()
    return jsonify({"ok": True, "task": task.to_dict()})


@app.route("/api/task/<int:task_id>", methods=["DELETE"])
def api_delete_task(task_id):
    """删除单个任务"""
    task = db.session.get(DailyTask, task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"ok": True})


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


# ─── 云端推送触发器（供 Render Cron 调用）───────

@app.route("/api/push/preview")
def api_push_preview():
    """触发晚间预览推送"""
    from daily_preview import main as preview_main
    try:
        preview_main()
        return jsonify({"ok": True, "type": "preview"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/push/morning")
def api_push_morning():
    """触发早安推送"""
    from morning_push import main as morning_main
    try:
        morning_main()
        return jsonify({"ok": True, "type": "morning"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── 启动入口 ─────────────────────────────────────────────

if __name__ == "__main__":
    import os as _os
    is_prod = _os.environ.get("RENDER") == "1"

    if is_prod:
        # 云端环境：启动 APScheduler 定时推送
        from apscheduler.schedulers.background import BackgroundScheduler
        from daily_preview import main as _preview_main
        from morning_push import main as _morning_main
        import atexit

        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        _scheduler.add_job(_preview_main, "cron", hour=PREVIEW_HOUR, minute=0, id="preview")
        _scheduler.add_job(_morning_main, "cron", hour=MORNING_HOUR, minute=0, id="morning")
        _scheduler.start()
        atexit.register(lambda: _scheduler.shutdown())
        print(f"[SCHEDULER] Push jobs registered: {PREVIEW_HOUR:02d}:00 & {MORNING_HOUR:02d}:00 CST")

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

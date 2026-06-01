"""数据库模型"""

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, Date, Text, DateTime, Enum, ForeignKey
import enum

db = SQLAlchemy()


class PlanStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class ConfirmStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ADJUSTED = "adjusted"
    EXPIRED = "expired"


class TaskPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Subject(str, enum.Enum):
    MATH = "math"
    ENGLISH = "english"


class Plan(db.Model):
    __tablename__ = "plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default=PlanStatus.ACTIVE.value)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    tasks = db.relationship("DailyTask", back_populates="plan", cascade="all, delete-orphan")
    summaries = db.relationship("WeeklySummary", back_populates="plan", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "exam_date": self.exam_date.isoformat() if self.exam_date else None,
            "status": self.status,
            "days_remaining": (self.exam_date - date.today()).days if self.exam_date else 0,
        }


class DailyTask(db.Model):
    __tablename__ = "daily_tasks"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    task_date = db.Column(db.Date, nullable=False, index=True)
    subject = db.Column(db.String(20), nullable=False)  # "math" / "english"
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default="")
    estimated_minutes = db.Column(db.Integer, default=60)
    priority = db.Column(db.String(20), default=TaskPriority.MEDIUM.value)
    sort_order = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default=TaskStatus.PENDING.value)
    is_adjusted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("Plan", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "task_date": self.task_date.isoformat() if self.task_date else None,
            "subject": self.subject,
            "title": self.title,
            "description": self.description,
            "estimated_minutes": self.estimated_minutes,
            "priority": self.priority,
            "sort_order": self.sort_order,
            "status": self.status,
            "is_adjusted": self.is_adjusted,
        }


class Confirmation(db.Model):
    __tablename__ = "confirmations"

    id = db.Column(db.Integer, primary_key=True)
    confirm_date = db.Column(db.Date, nullable=False, index=True, unique=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), default=ConfirmStatus.PENDING.value)
    preview_msg_sent = db.Column(db.Boolean, default=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WeeklySummary(db.Model):
    __tablename__ = "weekly_summaries"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    week_end = db.Column(db.Date, nullable=False)
    completion_rate = db.Column(db.Float, default=0.0)
    ai_feedback = db.Column(db.Text, default="")
    next_week_adjusted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("Plan", back_populates="summaries")


def init_db(app):
    """初始化数据库，创建所有表"""
    import os
    db_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(db_dir, exist_ok=True)
    with app.app_context():
        db.create_all()

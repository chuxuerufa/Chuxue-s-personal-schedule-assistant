"""飞书推送封装 —— 交互式卡片消息构建 + Webhook 发送"""

import json
import requests
from datetime import date, timedelta
from config import FEISHU_WEBHOOK_URL


# 飞书卡片颜色常量
COLORS = {
    "math": "blue",
    "english": "green",
    "rest": "grey",
}

SUBJECT_EMOJI = {
    "math": "📐",
    "english": "📝",
    "rest": "😴",
}

PRIORITY_LABEL = {
    "high": "⭐",
    "medium": "  ",
    "low": "   ",
}


def send_card_message(webhook_url: str, card: dict) -> bool:
    """发送飞书交互式卡片消息"""
    payload = {
        "msg_type": "interactive",
        "card": card,
    }
    resp = requests.post(webhook_url, json=payload, timeout=10)
    result = resp.json()
    if result.get("code") != 0:
        print(f"[Feishu Push Failed] code={result.get('code')} msg={result.get('msg')}")
        return False
    return True


def send_text_message(webhook_url: str, text: str) -> bool:
    """发送纯文本消息（备用）"""
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    resp = requests.post(webhook_url, json=payload, timeout=10)
    return resp.json().get("code") == 0


def build_preview_card(
    tasks: list[dict],
    target_date: date,
    confirm_url: str,
    adjust_url: str,
) -> dict:
    """
    构建「明日计划预览」飞书卡片
    tasks: [{"subject": "math", "title": "...", "estimated_minutes": 45, "priority": "high"}, ...]
    confirm_url: 确认按钮跳转链接
    adjust_url: 调整按钮跳转链接
    """
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday = weekday_names[target_date.weekday()]
    date_str = f"{target_date.month}月{target_date.day}日"

    # 按科目分组
    math_tasks = [t for t in tasks if t.get("subject") == "math"]
    eng_tasks = [t for t in tasks if t.get("subject") == "english"]
    total_minutes = sum(t.get("estimated_minutes", 0) for t in tasks)

    elements = []

    # 高数部分
    if math_tasks:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "📐 **高数**",
            }
        })
        for t in math_tasks:
            p = PRIORITY_LABEL.get(t.get("priority", "medium"), "  ")
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"　{p} {t['title']}（{t.get('estimated_minutes', 60)}分钟）",
                }
            })

    # 英语部分
    if eng_tasks:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "📝 **英语**",
            }
        })
        for t in eng_tasks:
            p = PRIORITY_LABEL.get(t.get("priority", "medium"), "  ")
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"　{p} {t['title']}（{t.get('estimated_minutes', 60)}分钟）",
                }
            })

    # 分隔线 + 总计
    elements.append({"tag": "hr"})
    hours = total_minutes // 60
    mins = total_minutes % 60
    time_str = f"{hours}小时{mins}分钟" if hours > 0 else f"{mins}分钟"
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"⏱ 预计总时长：**{time_str}**",
        }
    })

    # 备注
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": "请在今晚 24:00 前确认，未确认将按默认计划执行",
        }],
    })

    card = {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📅 明天（{date_str} {weekday}）学习计划预览",
            },
            "template": "indigo",
        },
        "elements": elements,
        "config": {
            "wide_screen_mode": True,
        },
    }

    # 只在有 URL 时添加按钮
    if confirm_url or adjust_url:
        actions = []
        if confirm_url:
            actions.append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": "✅ 确认计划"},
                "type": "primary",
                "url": confirm_url,
            })
        if adjust_url:
            actions.append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": "✏️ 调整计划"},
                "type": "default",
                "url": adjust_url,
            })
        card["elements"].append({"tag": "action", "actions": actions})

    return card


def build_morning_card(
    tasks: list[dict],
    plan_name: str,
    days_remaining: int,
    streak: int = 0,
    detail_url: str = "",
) -> dict:
    """
    构建「早安推送」飞书卡片
    """
    today = date.today()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday = weekday_names[today.weekday()]
    date_str = f"{today.month}月{today.day}日"

    # 按科目分组
    math_tasks = [t for t in tasks if t.get("subject") == "math"]
    eng_tasks = [t for t in tasks if t.get("subject") == "english"]
    total_tasks = len(tasks)

    elements = []

    # 倒计时
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"📅 {date_str} {weekday}　|　⏳ 距考试还有 **{days_remaining}** 天",
        }
    })
    elements.append({"tag": "hr"})

    # 任务列表
    if math_tasks:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "📐 **高数**"},
        })
        for t in math_tasks:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"　• {t['title']}（{t.get('estimated_minutes', 60)}分钟）",
                }
            })

    if eng_tasks:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "📝 **英语**"},
        })
        for t in eng_tasks:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"　• {t['title']}（{t.get('estimated_minutes', 60)}分钟）",
                }
            })

    elements.append({"tag": "hr"})

    # 鼓励语
    if streak >= 7:
        msg = f"🔥 连续打卡 **{streak}** 天！太厉害了，继续保持！"
    elif streak >= 3:
        msg = f"💪 连续打卡 **{streak}** 天，状态不错，加油！"
    elif streak > 0:
        msg = f"🌟 已连续打卡 **{streak}** 天，今天也要坚持哦！"
    else:
        msg = "🌱 新的一天，从完成计划开始！"

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": msg},
    })

    # 详情链接按钮
    if detail_url:
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "📋 打开详情，开始今日学习"},
                "type": "primary",
                "url": detail_url,
            }],
        })

    time_str = ""
    total_minutes = sum(t.get("estimated_minutes", 0) for t in tasks)
    if total_minutes > 0:
        hours = total_minutes // 60
        mins = total_minutes % 60
        time_str = f"总时长 {hours}h{mins}min · " if hours > 0 else f"总时长 {mins}min · "

    return {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🌅 早上好！今日学习计划已就绪",
            },
            "template": "blue",
        },
        "elements": elements,
        "config": {
            "wide_screen_mode": True,
        },
    }

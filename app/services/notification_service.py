"""
Sends Telegram messages directly via Bot API.
Used by scheduled jobs (evening ritual, morning briefing).
"""
import os
import logging
import aiohttp
from datetime import date

from datetime import date as date_type
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.i18n import t
from app.services.daily_plan_service import get_assembled_day

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _task_urgency_key(task, today: date_type):
    due = task.due_date
    prio = _PRIORITY_ORDER.get(task.priority or "", 2)
    if due and due < today:
        return (0, due, prio)
    if due and due == today:
        return (1, date_type.min, prio)
    return (2, due or date_type.max, prio)

logger = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/sendMessage"


async def _send(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping notification")
        return
    url = TG_API.format(token=token)
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error("TG sendMessage failed: %s %s", resp.status, body)


def _fmt_time(t_obj) -> str:
    return t_obj.strftime("%H:%M") if t_obj else ""


async def send_morning_briefing(user: User, db: AsyncSession) -> None:
    """Send morning briefing to a user."""
    if not user.telegram_id:
        return

    locale = user.locale or "en"
    today = date.today()
    day_view = await get_assembled_day(user, today, db)

    lines = [t("morning_greeting", locale).format(name=user.name), ""]

    if day_view.schedule_items:
        for item in day_view.schedule_items:
            lines.append(f"🕐 {_fmt_time(item.time_start)} {item.title}")

    if day_view.events:
        for event in day_view.events:
            time_str = f" {_fmt_time(event.time_start)}" if event.time_start else ""
            lines.append(f"📅{time_str} {event.title}")

    if day_view.tasks:
        sorted_tasks = sorted(day_view.tasks, key=lambda task: _task_urgency_key(task, today))
        for task in sorted_tasks:
            time_str = f" {_fmt_time(task.time_start)}" if task.time_start else ""
            due = task.due_date
            if due and due < today:
                days_over = (today - due).days
                label = f" · {t('task_overdue', locale).format(days=days_over)}"
                emoji = "🔥"
            elif due and due == today:
                label = f" · {t('task_due_today', locale)}"
                emoji = "🔥"
            else:
                label = f" · {due.strftime('%b %d')}" if due else ""
                emoji = "📝"
            lines.append(f"{emoji}{time_str} {task.title}{label}")

    if not (day_view.schedule_items or day_view.events or day_view.tasks):
        lines.append(t("morning_free_day", locale))

    lines += ["", t("morning_footer", locale)]

    await _send(user.telegram_id, "\n".join(lines))


async def send_task_assigned(task, assignee: User, assigner: User) -> None:
    """Notify a user that a task was assigned to them."""
    if not assignee.telegram_id:
        return
    if assignee.id == assigner.id:
        return  # Don't notify when you assign to yourself
    locale = assignee.locale or "en"
    text = (
        f"📋 <b>{t('task_assigned_title', locale)}</b>\n\n"
        f"<b>{task.title}</b>\n"
        f"{t('task_assigned_by', locale).format(name=assigner.name)}"
    )
    await _send(assignee.telegram_id, text)


async def send_evening_ritual_prompt(owner: User, children: list[User]) -> None:
    """Remind owner/member to plan tomorrow. With children — family ritual; without — solo reminder."""
    if not owner.telegram_id:
        return
    locale = owner.locale or "en"
    if not children:
        text = t("evening_reminder_solo", locale) + "\n\n👉 /tonight"
    elif len(children) == 1:
        header = t("evening_ritual_prompt", locale).format(name=children[0].name)
        text = header + "\n\n" + t("evening_ritual_body", locale) + "\n\n👉 /tonight"
    else:
        names_list = "\n".join(f"• {c.name}" for c in children)
        header = t("evening_ritual_prompt_multi", locale) + "\n\n" + names_list
        text = header + "\n\n" + t("evening_ritual_body", locale) + "\n\n👉 /tonight"
    await _send(owner.telegram_id, text)

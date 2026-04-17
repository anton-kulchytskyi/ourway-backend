"""
Sends Telegram messages directly via Bot API.
Used by scheduled jobs (evening ritual, morning briefing).
"""
import os
import logging
import aiohttp
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.i18n import t
from app.services.daily_plan_service import get_assembled_day

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
        for task in day_view.tasks:
            time_str = f" {_fmt_time(task.time_start)}" if task.time_start else ""
            lines.append(f"✅{time_str} {task.title}")

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
    """Remind owner to plan tomorrow with their children (one message for all)."""
    if not owner.telegram_id or not children:
        return
    locale = owner.locale or "en"
    if len(children) == 1:
        header = t("evening_ritual_prompt", locale).format(name=children[0].name)
    else:
        names_list = "\n".join(f"• {c.name}" for c in children)
        header = t("evening_ritual_prompt_multi", locale) + "\n\n" + names_list
    text = header + "\n\n" + t("evening_ritual_body", locale) + "\n\n👉 /tonight"
    await _send(owner.telegram_id, text)

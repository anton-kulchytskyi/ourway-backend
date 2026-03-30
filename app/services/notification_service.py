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


async def _send(chat_id: int, text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping notification")
        return
    url = TG_API.format(token=token)
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
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
    day_view = await get_assembled_day(user.id, today, db)

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


async def send_evening_ritual_prompt(owner: User, child: User) -> None:
    """Remind owner to plan tomorrow with child."""
    if not owner.telegram_id:
        return
    locale = owner.locale or "en"
    text = (
        t("evening_ritual_prompt", locale).format(name=child.name)
        + "\n\n"
        + t("evening_ritual_body", locale)
    )
    await _send(owner.telegram_id, text)

"""
Sends Telegram messages directly via Bot API.
Used by scheduled jobs (evening ritual, morning briefing).
"""
import os
import logging
import aiohttp
from datetime import date, timedelta

from datetime import date as date_type
from sqlalchemy import select, any_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.task import Task
from app.models.event import Event
from app.models.schedule import Schedule
from app.core.i18n import t
from app.services.daily_plan_service import get_assembled_day

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _to_date(val) -> date_type | None:
    """Normalize datetime or date to date, handling DB returning datetime for date columns."""
    if val is None:
        return None
    return val.date() if hasattr(val, "date") and callable(val.date) else val


def _task_urgency_key(task, today: date_type):
    due = _to_date(task.due_date)
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

    # Own schedule
    if day_view.schedule_items:
        for item in day_view.schedule_items:
            lines.append(f"🕐 {_fmt_time(item.time_start)} {item.title}")

    # Children's schedules (for owners and members)
    if user.role in (UserRole.owner, UserRole.member) and user.organization_id:
        children_result = await db.execute(
            select(User).where(
                User.organization_id == user.organization_id,
                User.role == UserRole.child,
            )
        )
        children = children_result.scalars().all()

        if children:
            weekday = today.isoweekday()
            any_child_schedule = False
            child_lines = []
            for child in children:
                sched_result = await db.execute(
                    select(Schedule).where(
                        Schedule.user_id == child.id,
                        weekday == any_(Schedule.weekdays),
                        or_(Schedule.valid_from == None, Schedule.valid_from <= today),  # noqa: E711
                        or_(Schedule.valid_until == None, Schedule.valid_until >= today),  # noqa: E711
                    )
                )
                child_schedules = sorted(sched_result.scalars().all(), key=lambda s: s.time_start)
                if child_schedules:
                    any_child_schedule = True
                    sched_str = ", ".join(
                        f"{_fmt_time(s.time_start)} {s.title}" for s in child_schedules
                    )
                    child_lines.append(f"🧒 {child.name}: {sched_str}")

            if any_child_schedule:
                lines.append("")
                lines.append(t("morning_kids_section", locale))
                lines.extend(child_lines)

    # Events today
    if day_view.events:
        lines.append("")
        for event in day_view.events:
            time_str = f" {_fmt_time(event.time_start)}" if event.time_start else ""
            lines.append(f"📅{time_str} {event.title}")

    # All active tasks: todo + in_progress + overdue
    tasks_result = await db.execute(
        select(Task).where(
            Task.assignee_id == user.id,
            Task.status.notin_(["done", "blocked"]),
        )
    )
    all_tasks = tasks_result.scalars().all()

    morning_tasks = [
        task for task in all_tasks
        if task.status in ("in_progress", "todo")
        or (_to_date(task.due_date) and _to_date(task.due_date) <= today)
    ]
    morning_tasks.sort(key=lambda task: _task_urgency_key(task, today))

    if morning_tasks:
        lines.append("")
        for task in morning_tasks:
            due = _to_date(task.due_date)
            if due and due < today:
                days_over = (today - due).days
                label = f" · {t('task_overdue', locale).format(days=days_over)}"
                emoji = "🔥"
            elif due and due == today:
                label = f" · {t('task_due_today', locale)}"
                emoji = "🔥"
            else:
                emoji = "🔄" if task.status == "in_progress" else "📝"
                label = ""
            lines.append(f"{emoji} {task.title}{label}")

    if not (day_view.schedule_items or day_view.events or morning_tasks):
        lines.append(t("morning_free_day", locale))

    lines += ["", t("morning_footer", locale)]

    await _send(user.telegram_id, "\n".join(lines))


async def send_task_done_request(task, child: User, parent: User) -> None:
    """Notify parent that a child wants to mark a task as done."""
    if not parent.telegram_id:
        return
    locale = parent.locale or "en"
    child_tg_id = child.telegram_id or 0
    text = t("task_done_request", locale).format(name=child.name, title=task.title)
    reply_markup = {
        "inline_keyboard": [[
            {
                "text": t("task_done_approve_btn", locale),
                "callback_data": f"task_approve:{task.id}:{child_tg_id}",
            },
            {
                "text": t("task_done_reject_btn", locale),
                "callback_data": f"task_reject:{task.id}:{child_tg_id}",
            },
        ]]
    }
    await _send(parent.telegram_id, text, reply_markup=reply_markup)


async def send_child_task_activity(
    task,
    child: User,
    db: AsyncSession,
    *,
    is_done: bool,
) -> None:
    """Notify the task creator when a child completes a task or updates progress."""
    if not task.creator_id or task.creator_id == child.id:
        return
    result = await db.execute(select(User).where(User.id == task.creator_id))
    creator = result.scalar_one_or_none()
    if not creator or not creator.telegram_id:
        return
    locale = creator.locale or "en"
    if is_done:
        text = t("task_done_by_child", locale).format(name=child.name, title=task.title)
    else:
        current = task.progress_current or 0
        total = task.progress_total or 0
        text = t("task_progress_by_child", locale).format(
            name=child.name, title=task.title, current=current, total=total
        )
    await _send(creator.telegram_id, text)


async def send_plan_ready_to_child(child: User, parent_name: str) -> None:
    """Notify child that their plan for tomorrow was confirmed by a parent."""
    if not child.telegram_id or child.is_managed:
        return
    locale = child.locale or "en"
    text = t("plan_ready_for_child", locale).format(name=parent_name)
    await _send(child.telegram_id, text)


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


async def send_evening_ritual_prompt(owner: User, children: list[User], db: AsyncSession) -> None:
    """Remind owner/member to plan tomorrow. Includes in-progress tasks, overdue tasks, tomorrow events."""
    if not owner.telegram_id:
        return
    locale = owner.locale or "en"
    today = date.today()
    tomorrow = today + timedelta(days=1)

    if not children:
        header = t("evening_reminder_solo", locale)
    elif len(children) == 1:
        header = t("evening_ritual_prompt", locale).format(name=children[0].name)
        header += "\n\n" + t("evening_ritual_body", locale)
    else:
        names_list = "\n".join(f"• {c.name}" for c in children)
        header = t("evening_ritual_prompt_multi", locale) + "\n\n" + names_list
        header += "\n\n" + t("evening_ritual_body", locale)

    lines = [header]

    # In-progress tasks
    inprogress_result = await db.execute(
        select(Task).where(
            Task.assignee_id == owner.id,
            Task.status == "in_progress",
        )
    )
    inprogress_tasks = inprogress_result.scalars().all()

    # Overdue tasks that are NOT in_progress (backlog/todo past due)
    overdue_result = await db.execute(
        select(Task).where(
            Task.assignee_id == owner.id,
            Task.due_date < today,
            Task.status.notin_(["done", "blocked", "in_progress"]),
        )
    )
    overdue_tasks = overdue_result.scalars().all()

    if inprogress_tasks:
        lines.append("")
        lines.append(t("evening_inprogress_header", locale))
        for task in inprogress_tasks:
            due = _to_date(task.due_date)
            if due and due < today:
                days_over = (today - due).days
                label = f" · {t('task_overdue', locale).format(days=days_over)}"
            else:
                label = ""
            lines.append(f"🔄 {task.title}{label}")

    if overdue_tasks:
        lines.append("")
        lines.append(t("evening_overdue_header", locale))
        for task in sorted(overdue_tasks, key=lambda t_: _to_date(t_.due_date)):
            days_over = (today - _to_date(task.due_date)).days
            lines.append(f"🔥 {task.title} · {t('task_overdue', locale).format(days=days_over)}")

    # Tomorrow's events
    if owner.organization_id:
        events_result = await db.execute(
            select(Event).where(
                Event.organization_id == owner.organization_id,
                Event.date == tomorrow,
            )
        )
        all_events = events_result.scalars().all()
        tomorrow_events = [
            e for e in all_events if owner.id in (e.participants or [])
        ]
        tomorrow_events.sort(key=lambda e: (e.time_start is None, e.time_start))

        if tomorrow_events:
            lines.append("")
            lines.append(t("evening_tomorrow_events_header", locale))
            for event in tomorrow_events:
                time_str = f" {_fmt_time(event.time_start)}" if event.time_start else ""
                lines.append(f"📅{time_str} {event.title}")

    lines += ["", "👉 /tonight"]

    await _send(owner.telegram_id, "\n".join(lines))

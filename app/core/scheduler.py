import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


def _morning_job_id(user_id: int) -> str:
    return f"morning_user_{user_id}"


def _evening_job_id(user_id: int) -> str:
    return f"evening_user_{user_id}"


def ensure_user_jobs(user: User) -> None:
    """Create or replace morning + evening jobs for a single user.

    Safe to call any time — replaces existing jobs. Only schedules if the
    user has a telegram_id (no point sending briefings without TG).
    """
    if not user.telegram_id:
        return

    tz = user.timezone or "UTC"

    try:
        scheduler.add_job(
            morning_briefing_user_job,
            CronTrigger(
                hour=user.morning_brief_time.hour,
                minute=user.morning_brief_time.minute,
                timezone=tz,
            ),
            id=_morning_job_id(user.id),
            args=[user.id],
            replace_existing=True,
        )
    except Exception:
        logger.exception("Failed to register morning job for user %s", user.id)

    try:
        scheduler.add_job(
            evening_ritual_user_job,
            CronTrigger(
                hour=user.evening_ritual_time.hour,
                minute=user.evening_ritual_time.minute,
                timezone=tz,
            ),
            id=_evening_job_id(user.id),
            args=[user.id],
            replace_existing=True,
        )
    except Exception:
        logger.exception("Failed to register evening job for user %s", user.id)


def remove_user_jobs(user_id: int) -> None:
    """Remove scheduled jobs for a user (e.g. on account deletion)."""
    for job_id in (_morning_job_id(user_id), _evening_job_id(user_id)):
        job = scheduler.get_job(job_id)
        if job:
            job.remove()


# ── Event reminder jobs ───────────────────────────────────────────────────────

def _event_reminder_job_id(event_id: int) -> str:
    return f"event_reminder_{event_id}"


def ensure_event_reminder_job(event, creator_tz: str = "UTC") -> None:
    """Schedule (or replace) a one-time reminder for an event.

    Safe to call on create/update — replaces any existing job.
    Removes the job if the event no longer qualifies (no time/reminder).
    """
    if not (event.date and event.time_start and event.remind_before_min):
        remove_event_reminder_job(event.id)
        return

    try:
        tz = pytz.timezone(creator_tz)
    except Exception:
        tz = pytz.UTC

    event_dt = datetime.combine(event.date, event.time_start)
    event_dt_aware = tz.localize(event_dt)
    remind_dt = event_dt_aware - timedelta(minutes=event.remind_before_min)

    if remind_dt <= datetime.now(tz=pytz.UTC):
        return

    try:
        scheduler.add_job(
            event_reminder_job,
            "date",
            run_date=remind_dt,
            id=_event_reminder_job_id(event.id),
            args=[event.id],
            replace_existing=True,
        )
        logger.info("Scheduled event reminder for event %s at %s", event.id, remind_dt)
    except Exception:
        logger.exception("Failed to schedule event reminder for event %s", event.id)


def remove_event_reminder_job(event_id: int) -> None:
    job_id = _event_reminder_job_id(event_id)
    job = scheduler.get_job(job_id)
    if job:
        job.remove()


async def event_reminder_job(event_id: int) -> None:
    from app.services.notification_service import send_event_reminder
    async with AsyncSessionLocal() as db:
        try:
            await send_event_reminder(event_id, db)
        except Exception:
            logger.exception("Failed to send event reminder for event %s", event_id)


async def morning_briefing_user_job(user_id: int) -> None:
    from app.services.notification_service import send_morning_briefing
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active or not user.telegram_id:
            return
        try:
            await send_morning_briefing(user, db)
        except Exception:
            logger.exception("Failed to send morning briefing to user %s", user_id)


async def evening_ritual_user_job(user_id: int) -> None:
    from app.services.notification_service import send_evening_ritual_prompt
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active or not user.telegram_id:
            return
        if user.role == UserRole.child:
            return
        if not user.organization_id:
            return
        children: list[User] = []
        if user.role == UserRole.owner:
            children_result = await db.execute(
                select(User).where(
                    User.organization_id == user.organization_id,
                    User.role == UserRole.child,
                )
            )
            children = list(children_result.scalars().all())
        try:
            await send_evening_ritual_prompt(user, children, db)
        except Exception:
            logger.exception("Failed to send evening ritual to user %s", user_id)


async def setup_scheduler() -> None:
    """Register per-user morning/evening jobs and upcoming event reminder jobs."""
    from datetime import date as date_type
    from app.models.event import Event

    try:
        async with AsyncSessionLocal() as db:
            users_result = await db.execute(
                select(User).where(
                    User.telegram_id != None,  # noqa: E711
                    User.is_active == True,    # noqa: E712
                )
            )
            users = users_result.scalars().all()

            for user in users:
                ensure_user_jobs(user)
            logger.info("Scheduler jobs registered for %d users", len(users))

            # Schedule reminders for upcoming events
            today = date_type.today()
            events_result = await db.execute(
                select(Event).where(
                    Event.date >= today,
                    Event.remind_before_min != None,  # noqa: E711
                    Event.time_start != None,         # noqa: E711
                )
            )
            events = events_result.scalars().all()

            creator_ids = {e.created_by for e in events if e.created_by}
            tz_map: dict[int, str] = {}
            if creator_ids:
                creators_result = await db.execute(
                    select(User).where(User.id.in_(creator_ids))
                )
                for u in creators_result.scalars().all():
                    tz_map[u.id] = u.timezone or "UTC"

            for event in events:
                tz = tz_map.get(event.created_by, "UTC") if event.created_by else "UTC"
                ensure_event_reminder_job(event, tz)
            logger.info("Scheduled reminder jobs for %d events", len(events))

    except Exception:
        logger.exception("Failed to set up scheduler")

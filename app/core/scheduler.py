import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")

MORNING_HOUR = 7
MORNING_MINUTE = 30
EVENING_HOUR = 21
EVENING_MINUTE = 0


def _tz_job_id(tz: str, prefix: str) -> str:
    """Stable job ID for a timezone, e.g. 'morning_Europe_Warsaw'."""
    return f"{prefix}_{tz.replace('/', '_').replace(' ', '_')}"


def ensure_timezone_jobs(tz: str) -> None:
    """Add morning + evening jobs for *tz* if not already registered.

    Safe to call at any time (e.g. from PATCH /users/me when user changes tz).
    """
    morning_id = _tz_job_id(tz, "morning")
    evening_id = _tz_job_id(tz, "evening")

    if not scheduler.get_job(morning_id):
        try:
            scheduler.add_job(
                morning_briefing_job,
                CronTrigger(hour=MORNING_HOUR, minute=MORNING_MINUTE, timezone=tz),
                id=morning_id,
                args=[tz],
                replace_existing=True,
            )
            logger.info("Registered morning job for timezone %s", tz)
        except Exception:
            logger.exception("Failed to register morning job for timezone %s", tz)

    if not scheduler.get_job(evening_id):
        try:
            scheduler.add_job(
                evening_ritual_job,
                CronTrigger(hour=EVENING_HOUR, minute=EVENING_MINUTE, timezone=tz),
                id=evening_id,
                args=[tz],
                replace_existing=True,
            )
            logger.info("Registered evening job for timezone %s", tz)
        except Exception:
            logger.exception("Failed to register evening job for timezone %s", tz)


async def morning_briefing_job(tz: str) -> None:
    """07:30 local time — send morning briefing to users in *tz*."""
    logger.info("Running morning briefing job for timezone %s", tz)
    from app.services.notification_service import send_morning_briefing
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.telegram_id != None,  # noqa: E711
                User.is_active == True,    # noqa: E712
                User.timezone == tz,
            )
        )
        users = result.scalars().all()
        for user in users:
            try:
                await send_morning_briefing(user, db)
            except Exception:
                logger.exception("Failed to send morning briefing to user %s", user.id)


async def evening_ritual_job(tz: str) -> None:
    """21:00 local time — remind owners in *tz* to plan tomorrow with children."""
    logger.info("Running evening ritual job for timezone %s", tz)
    from app.services.notification_service import send_evening_ritual_prompt
    async with AsyncSessionLocal() as db:
        owners_result = await db.execute(
            select(User).where(
                User.role == UserRole.owner,
                User.telegram_id != None,  # noqa: E711
                User.is_active == True,    # noqa: E712
                User.timezone == tz,
            )
        )
        owners = owners_result.scalars().all()

        for owner in owners:
            if not owner.organization_id:
                continue
            children_result = await db.execute(
                select(User).where(
                    User.organization_id == owner.organization_id,
                    User.role == UserRole.child,
                )
            )
            children = children_result.scalars().all()
            for child in children:
                try:
                    await send_evening_ritual_prompt(owner, child)
                except Exception:
                    logger.exception(
                        "Failed to send evening ritual to owner %s for child %s",
                        owner.id, child.id,
                    )


async def setup_scheduler() -> None:
    """Register per-timezone jobs for all timezones currently in the DB.

    UTC is always registered. Other timezones are loaded from users.timezone.
    """
    # Always ensure UTC jobs exist
    ensure_timezone_jobs("UTC")

    # Load all unique timezones from DB
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.timezone).where(User.timezone != None).distinct()  # noqa: E711
            )
            timezones = {row[0] for row in result.all() if row[0]}
    except Exception:
        logger.exception("Failed to load timezones from DB — falling back to UTC only")
        timezones = {"UTC"}

    for tz in timezones:
        ensure_timezone_jobs(tz)

    logger.info(
        "Scheduler jobs registered for timezones: %s",
        sorted(timezones),
    )

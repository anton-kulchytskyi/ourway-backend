import logging
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
        if user.role != UserRole.owner or not user.organization_id:
            return
        children_result = await db.execute(
            select(User).where(
                User.organization_id == user.organization_id,
                User.role == UserRole.child,
            )
        )
        children = children_result.scalars().all()
        if not children:
            return
        try:
            await send_evening_ritual_prompt(user, list(children))
        except Exception:
            logger.exception("Failed to send evening ritual to user %s", user_id)


async def setup_scheduler() -> None:
    """Register per-user jobs for all users with a telegram_id."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(
                    User.telegram_id != None,  # noqa: E711
                    User.is_active == True,    # noqa: E712
                )
            )
            users = result.scalars().all()
    except Exception:
        logger.exception("Failed to load users from DB for scheduler setup")
        return

    for user in users:
        ensure_user_jobs(user)

    logger.info("Scheduler jobs registered for %d users", len(users))

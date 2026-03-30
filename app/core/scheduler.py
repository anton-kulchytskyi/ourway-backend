import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


async def morning_briefing_job() -> None:
    """7:30 — send morning briefing to every user with telegram_id."""
    logger.info("Running morning briefing job")
    from app.services.notification_service import send_morning_briefing
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.telegram_id != None, User.is_active == True)  # noqa: E711
        )
        users = result.scalars().all()
        for user in users:
            try:
                await send_morning_briefing(user, db)
            except Exception:
                logger.exception("Failed to send morning briefing to user %s", user.id)


async def evening_ritual_job() -> None:
    """21:00 — remind owners to plan tomorrow with each of their children."""
    logger.info("Running evening ritual job")
    from app.services.notification_service import send_evening_ritual_prompt
    async with AsyncSessionLocal() as db:
        owners_result = await db.execute(
            select(User).where(
                User.role == UserRole.owner,
                User.telegram_id != None,  # noqa: E711
                User.is_active == True,    # noqa: E712
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


def setup_scheduler() -> None:
    scheduler.add_job(
        morning_briefing_job,
        CronTrigger(hour=7, minute=30, timezone="UTC"),
        id="morning_briefing",
        replace_existing=True,
    )
    scheduler.add_job(
        evening_ritual_job,
        CronTrigger(hour=21, minute=0, timezone="UTC"),
        id="evening_ritual",
        replace_existing=True,
    )
    logger.info("Scheduler jobs registered: morning_briefing (07:30 UTC), evening_ritual (21:00 UTC)")

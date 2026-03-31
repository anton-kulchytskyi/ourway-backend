from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, literal, any_
from datetime import date

from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.models.schedule import Schedule
from app.models.event import Event
from app.models.task import Task
from app.models.space import SpaceMember
from app.models.user import User
from app.schemas.daily_plan import (
    DailyPlanResponse,
    ScheduleItemOut,
    TaskItemOut,
    EventItemOut,
    DayView,
    FamilyMemberDay,
)


async def _get_or_create_plan(user_id: int, target_date: date, db: AsyncSession) -> DailyPlan:
    result = await db.execute(
        select(DailyPlan).where(DailyPlan.user_id == user_id, DailyPlan.date == target_date)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        plan = DailyPlan(user_id=user_id, date=target_date, status=DailyPlanStatus.draft)
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
    return plan


async def get_assembled_day(user_id: int, target_date: date, db: AsyncSession) -> DayView:
    plan = await _get_or_create_plan(user_id, target_date, db)

    # --- Schedules active on this weekday and date range ---
    weekday = target_date.isoweekday()  # 1=Mon, 7=Sun
    schedules_result = await db.execute(
        select(Schedule).where(
            Schedule.user_id == user_id,
            weekday == any_(Schedule.weekdays),
            or_(Schedule.valid_from == None, Schedule.valid_from <= target_date),  # noqa: E711
            or_(Schedule.valid_until == None, Schedule.valid_until >= target_date),  # noqa: E711
        )
    )
    schedules = schedules_result.scalars().all()
    schedule_items = [
        ScheduleItemOut(title=s.title, time_start=s.time_start, time_end=s.time_end)
        for s in sorted(schedules, key=lambda s: s.time_start)
    ]

    # --- User info for org_id ---
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    org_id = user.organization_id if user else None

    # --- Events on this date where user is a participant ---
    event_items: list[EventItemOut] = []
    if org_id:
        events_result = await db.execute(
            select(Event).where(
                Event.organization_id == org_id,
                Event.date == target_date,
            )
        )
        events = events_result.scalars().all()
        event_items = [
            EventItemOut(id=e.id, title=e.title, time_start=e.time_start, time_end=e.time_end)
            for e in events
            if user_id in (e.participants or [])
        ]
        event_items.sort(key=lambda e: (e.time_start is None, e.time_start))

    # --- Tasks: explicitly scheduled for this date ---
    tasks_result = await db.execute(
        select(Task).where(
            Task.assignee_id == user_id,
            Task.scheduled_date == target_date,
        )
    )
    tasks = list(tasks_result.scalars().all())

    # --- Auto-add tasks for child: spaces with auto_add_to_child_day=True ---
    if user and user.role.value == "child":
        auto_space_result = await db.execute(
            select(SpaceMember.space_id).where(
                SpaceMember.user_id == user_id,
                SpaceMember.auto_add_to_child_day == True,  # noqa: E712
            )
        )
        auto_space_ids = [row[0] for row in auto_space_result.all()]
        if auto_space_ids:
            auto_tasks_result = await db.execute(
                select(Task).where(
                    Task.space_id.in_(auto_space_ids),
                    Task.assignee_id == user_id,
                    Task.scheduled_date == None,  # noqa: E711
                    Task.status.notin_(["done", "blocked"]),
                )
            )
            existing_ids = {t.id for t in tasks}
            for t in auto_tasks_result.scalars().all():
                if t.id not in existing_ids:
                    tasks.append(t)

    task_items = [
        TaskItemOut(id=t.id, title=t.title, time_start=t.time_start, status=t.status, points=t.points)
        for t in sorted(tasks, key=lambda t: (t.time_start is None, t.time_start))
    ]

    return DayView(
        plan=DailyPlanResponse.model_validate(plan),
        schedule_items=schedule_items,
        events=event_items,
        tasks=task_items,
    )


async def get_family_day(org_id: int, target_date: date, db: AsyncSession) -> list[FamilyMemberDay]:
    members_result = await db.execute(
        select(User).where(User.organization_id == org_id)
    )
    members = members_result.scalars().all()

    result = []
    for member in members:
        day_view = await get_assembled_day(member.id, target_date, db)
        result.append(FamilyMemberDay(
            user_id=member.id,
            user_name=member.name,
            role=member.role.value,
            day=day_view,
        ))
    return result

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, any_, delete
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
        await db.execute(
            delete(DailyPlan).where(
                DailyPlan.user_id == user_id,
                DailyPlan.date < target_date,
                DailyPlan.status == DailyPlanStatus.draft,
            )
        )
        plan = DailyPlan(user_id=user_id, date=target_date, status=DailyPlanStatus.draft)
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
    return plan


async def _fetch_schedule_items(user_id: int, target_date: date, db: AsyncSession) -> list[ScheduleItemOut]:
    weekday = target_date.isoweekday()  # 1=Mon, 7=Sun
    result = await db.execute(
        select(Schedule).where(
            Schedule.user_id == user_id,
            weekday == any_(Schedule.weekdays),
            or_(Schedule.valid_from == None, Schedule.valid_from <= target_date),  # noqa: E711
            or_(Schedule.valid_until == None, Schedule.valid_until >= target_date),  # noqa: E711
        )
    )
    schedules = result.scalars().all()
    return [
        ScheduleItemOut(title=s.title, time_start=s.time_start, time_end=s.time_end)
        for s in sorted(schedules, key=lambda s: s.time_start)
    ]


async def _fetch_org_events(org_id: int, target_date: date, db: AsyncSession) -> list[Event]:
    result = await db.execute(
        select(Event).where(Event.organization_id == org_id, Event.date == target_date)
    )
    return list(result.scalars().all())


def _filter_event_items(events: list[Event], user_id: int) -> list[EventItemOut]:
    """Filter org events to those the user participates in, then sort by time."""
    items = [
        EventItemOut(id=e.id, title=e.title, time_start=e.time_start, time_end=e.time_end)
        for e in events
        if user_id in (e.participants or [])
    ]
    items.sort(key=lambda e: (e.time_start is None, e.time_start))
    return items


async def _fetch_task_items(user_id: int, target_date: date, is_child: bool, db: AsyncSession) -> list[TaskItemOut]:
    """Fetch tasks scheduled for the date, plus auto-added tasks for children."""
    tasks_result = await db.execute(
        select(Task).where(Task.assignee_id == user_id, Task.scheduled_date == target_date)
    )
    tasks = list(tasks_result.scalars().all())

    if is_child:
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

    return [
        TaskItemOut(id=t.id, title=t.title, time_start=t.time_start, status=t.status, points=t.points)
        for t in sorted(tasks, key=lambda t: (t.time_start is None, t.time_start))
    ]


async def get_assembled_day(user: User, target_date: date, db: AsyncSession) -> DayView:
    """Assemble a full day view (schedule + events + tasks) for a single user."""
    plan = await _get_or_create_plan(user.id, target_date, db)
    schedule_items = await _fetch_schedule_items(user.id, target_date, db)

    event_items: list[EventItemOut] = []
    if user.organization_id:
        events = await _fetch_org_events(user.organization_id, target_date, db)
        event_items = _filter_event_items(events, user.id)

    is_child = user.role.value == "child"
    task_items = await _fetch_task_items(user.id, target_date, is_child, db)

    return DayView(
        plan=DailyPlanResponse.model_validate(plan),
        schedule_items=schedule_items,
        events=event_items,
        tasks=task_items,
    )


async def get_family_day(org_id: int, target_date: date, db: AsyncSession) -> list[FamilyMemberDay]:
    """Assemble day views for all org members. Events are fetched once and shared."""
    members_result = await db.execute(select(User).where(User.organization_id == org_id))
    members = members_result.scalars().all()

    # Fetch org events once — same for everyone in the org
    shared_events = await _fetch_org_events(org_id, target_date, db)

    result = []
    for member in members:
        plan = await _get_or_create_plan(member.id, target_date, db)
        schedule_items = await _fetch_schedule_items(member.id, target_date, db)
        event_items = _filter_event_items(shared_events, member.id)
        is_child = member.role.value == "child"
        task_items = await _fetch_task_items(member.id, target_date, is_child, db)

        result.append(FamilyMemberDay(
            user_id=member.id,
            user_name=member.name,
            role=member.role.value,
            day=DayView(
                plan=DailyPlanResponse.model_validate(plan),
                schedule_items=schedule_items,
                events=event_items,
                tasks=task_items,
            ),
        ))
    return result

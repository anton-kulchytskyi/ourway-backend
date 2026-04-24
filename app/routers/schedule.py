from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse

router = APIRouter(prefix="/schedule", tags=["schedule"])


async def _get_schedule_or_404(schedule_id: int, current_user: User, db: AsyncSession) -> Schedule:
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    # owner and member can access any schedule; children only their own
    if current_user.role == UserRole.child and schedule.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return schedule


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns schedules. By default returns current user's schedules.
    Owner/member can pass user_id to view a family member's schedule.
    """
    if user_id and current_user.role == UserRole.child:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    target_id = user_id if user_id else current_user.id
    result = await db.execute(select(Schedule).where(Schedule.user_id == target_id))
    return result.scalars().all()


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: ScheduleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.child:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Children cannot create schedules")

    target_user_id = body.user_id if body.user_id else current_user.id

    # Only owner and member can create schedules for other users
    if target_user_id != current_user.id and current_user.role not in (UserRole.owner, UserRole.member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can create schedules for others")

    schedule = Schedule(
        title=body.title,
        weekdays=body.weekdays,
        time_start=body.time_start,
        time_end=body.time_end,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
        user_id=target_user_id,
        created_by=current_user.id,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await _get_schedule_or_404(schedule_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await _get_schedule_or_404(schedule_id, current_user, db)
    await db.delete(schedule)
    await db.commit()

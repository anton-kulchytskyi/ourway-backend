from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime, timezone

from app.database import get_db
from app.core.deps import get_current_user, get_current_org_user
from app.models.user import User, UserRole
from app.models.daily_plan import DailyPlan, DailyPlanStatus
from app.schemas.daily_plan import DailyPlanCreate, DailyPlanResponse, DayView, FamilyMemberDay
from app.services.daily_plan_service import (
    get_assembled_day,
    get_family_day,
    _get_or_create_plan,
)

router = APIRouter(prefix="/day", tags=["daily_plan"])


@router.get("", response_model=DayView)
async def get_day(
    date: date,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get assembled daily plan (schedule + events + tasks) for a given date."""
    if user_id and current_user.role == UserRole.child:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    target_id = user_id if user_id else current_user.id
    return await get_assembled_day(target_id, date, db)


@router.post("/confirm", response_model=DailyPlanResponse)
async def confirm_day(
    body: DailyPlanCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm a daily plan (by parent or child)."""
    target_id = body.user_id if body.user_id else current_user.id

    if target_id != current_user.id and current_user.role not in (UserRole.owner, UserRole.member):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    plan = await _get_or_create_plan(target_id, body.date, db)

    if plan.status == DailyPlanStatus.completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan is already completed")

    plan.status = DailyPlanStatus.confirmed
    plan.confirmed_at = datetime.now(timezone.utc)
    plan.confirmed_by = current_user.id
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/family", response_model=list[FamilyMemberDay])
async def get_family_day_view(
    date: date,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):
    """Get assembled daily plans for all family members (owner/member only)."""
    if current_user.role == UserRole.child:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return await get_family_day(current_user.organization_id, date, db)

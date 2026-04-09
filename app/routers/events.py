from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from datetime import date

from app.database import get_db
from app.core.deps import get_current_org_user
from app.models.user import User, UserRole
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate, EventResponse

router = APIRouter(prefix="/events", tags=["events"])


async def _get_event_or_404(event_id: int, current_user: User, db: AsyncSession) -> Event:
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return event


@router.get("", response_model=list[EventResponse])
async def list_events(
    date: date | None = None,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):
    """List events for the current user's organization, optionally filtered by date."""

    query = select(Event).where(Event.organization_id == current_user.organization_id)
    if date:
        query = query.where(Event.date == date)

    result = await db.execute(query)
    events = result.scalars().all()

    # Child only sees events they participate in
    if current_user.role == UserRole.child:
        events = [e for e in events if current_user.id in (e.participants or [])]

    return events


@router.post("", response_model=EventResponse, status_code=201)
async def create_event(
    body: EventCreate,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.child:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Children cannot create events")

    event = Event(
        title=body.title,
        organization_id=current_user.organization_id,
        date=body.date,
        time_start=body.time_start,
        time_end=body.time_end,
        is_fixed=body.is_fixed,
        duration_min=body.duration_min,
        find_before=body.find_before,
        participants=body.participants,
        created_by=current_user.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    body: EventUpdate,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.child:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Children cannot edit events")

    event = await _get_event_or_404(event_id, current_user, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    await db.commit()
    await db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.child:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Children cannot delete events")

    event = await _get_event_or_404(event_id, current_user, db)
    await db.delete(event)
    await db.commit()

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.space import Space
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _check_space_access(space_id: int, org_id: int, db: AsyncSession) -> Space:
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.organization_id == org_id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    return space


async def _get_task_or_404(task_id: int, org_id: int, db: AsyncSession) -> Task:
    result = await db.execute(
        select(Task)
        .join(Space, Task.space_id == Space.id)
        .where(Task.id == task_id, Space.organization_id == org_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    space_id: int | None = None,
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    query = (
        select(Task)
        .join(Space, Task.space_id == Space.id)
        .where(Space.organization_id == current_user.organization_id)
    )
    if space_id:
        query = query.where(Task.space_id == space_id)
    if status:
        query = query.where(Task.status == status)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    await _check_space_access(body.space_id, current_user.organization_id, db)

    task = Task(
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        points=body.points,
        due_date=body.due_date,
        space_id=body.space_id,
        creator_id=current_user.id,
        assignee_id=body.assignee_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")
    return await _get_task_or_404(task_id, current_user.organization_id, db)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    task = await _get_task_or_404(task_id, current_user.organization_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    task = await _get_task_or_404(task_id, current_user.organization_id, db)
    await db.delete(task)
    await db.commit()

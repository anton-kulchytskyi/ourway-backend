from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database import get_db
from app.core.deps import get_current_org_user
from app.core.i18n import t
from app.models.user import User, UserRole
from app.models.task import Task
from app.models.space import Space, SpaceMember, SpaceMemberRole
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.services.notification_service import send_task_assigned, send_child_task_activity

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _check_space_access(space_id: int, user_id: int, db: AsyncSession, require_editor: bool = False, locale: str = "en") -> Space:
    result = await db.execute(
        select(Space)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(Space.id == space_id, SpaceMember.user_id == user_id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    if require_editor:
        m_result = await db.execute(
            select(SpaceMember).where(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
        )
        m = m_result.scalar_one_or_none()
        if m and m.role == SpaceMemberRole.viewer:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("viewers_cannot_modify_tasks", locale))
    return space


async def _get_task_or_404(task_id: int, user_id: int, db: AsyncSession) -> Task:
    result = await db.execute(
        select(Task)
        .join(Space, Task.space_id == Space.id)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(Task.id == task_id, SpaceMember.user_id == user_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    space_id: int | None = None,
    status: str | None = None,
    assignee_id: int | None = None,
    mine: bool = False,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):

    query = (
        select(Task)
        .join(Space, Task.space_id == Space.id)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(SpaceMember.user_id == current_user.id)
    )
    if space_id:
        query = query.where(Task.space_id == space_id)
    if status:
        query = query.where(Task.status == status)
    if mine:
        query = query.where(
            (Task.assignee_id == current_user.id) |
            ((Task.assignee_id == None) & (Task.creator_id == current_user.id))  # noqa: E711
        )
    elif assignee_id:
        query = query.where(Task.assignee_id == assignee_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):

    await _check_space_access(body.space_id, current_user.id, db, require_editor=True, locale=current_user.locale)

    task = Task(
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        points=body.points,
        due_date=body.due_date,
        scheduled_date=body.scheduled_date,
        space_id=body.space_id,
        creator_id=current_user.id,
        assignee_id=body.assignee_id if body.assignee_id is not None else current_user.id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    if body.assignee_id and body.assignee_id != current_user.id:
        assignee_result = await db.execute(select(User).where(User.id == body.assignee_id))
        assignee = assignee_result.scalar_one_or_none()
        if assignee:
            await send_task_assigned(task, assignee, current_user)

    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_task_or_404(task_id, current_user.id, db)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):

    task = await _get_task_or_404(task_id, current_user.id, db)
    prev_assignee_id = task.assignee_id
    prev_status = task.status
    prev_progress_current = task.progress_current

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)

    new_assignee_id = task.assignee_id
    if (
        new_assignee_id
        and new_assignee_id != prev_assignee_id
        and new_assignee_id != current_user.id
    ):
        assignee_result = await db.execute(select(User).where(User.id == new_assignee_id))
        assignee = assignee_result.scalar_one_or_none()
        if assignee:
            await send_task_assigned(task, assignee, current_user)

    if current_user.role == UserRole.child:
        status_done = task.status == "done" and prev_status != "done"
        progress_changed = (
            task.progress_current is not None
            and task.progress_current != prev_progress_current
        )
        if status_done:
            await send_child_task_activity(task, current_user, db, is_done=True)
        elif progress_changed:
            await send_child_task_activity(task, current_user, db, is_done=False)

    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_org_user),
    db: AsyncSession = Depends(get_db),
):

    if current_user.role.value == "child" and current_user.autonomy_level in (1, 2):
        raise HTTPException(status_code=403, detail="Children at this autonomy level cannot delete tasks")

    task = await _get_task_or_404(task_id, current_user.id, db)
    await db.delete(task)
    await db.commit()

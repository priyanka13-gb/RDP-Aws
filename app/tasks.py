"""Optional task API; schema creation is an explicit operator action."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, String, Text, Uuid, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class TaskStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus = TaskStatus.pending


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus | None = None

    @field_validator("title", "status")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_in_utc(cls, value):
        return value.astimezone(UTC)


def database_session(request: Request):
    if not request.app.state.settings.task_api_enabled:
        raise HTTPException(status_code=503, detail="Task API is disabled")
    engine = request.app.state.database_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Task database is not configured")
    try:
        with Session(engine) as session:
            yield session
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Task database is unavailable") from None


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
Db = Annotated[Session, Depends(database_session)]


def get_task_or_404(db: Session, task_id: uuid.UUID) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(data: TaskCreate, db: Db):
    task = Task(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    db: Db,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: TaskStatus | None = None,
):
    query = select(Task).order_by(Task.created_at, Task.id).offset(offset).limit(limit)
    if status is not None:
        query = query.where(Task.status == status.value)
    return db.scalars(query).all()


@router.get("/{task_id}", response_model=TaskOut)
def read_task(task_id: uuid.UUID, db: Db):
    return get_task_or_404(db, task_id)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: uuid.UUID, data: TaskUpdate, db: Db):
    task = get_task_or_404(db, task_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: uuid.UUID, db: Db):
    db.delete(get_task_or_404(db, task_id))
    db.commit()
    return Response(status_code=204)

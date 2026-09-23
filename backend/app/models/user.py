from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.worklog import Worklog


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_github_login", "github_login"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    github_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    github_login: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    worklogs: Mapped[list[Worklog]] = relationship(back_populates="user")

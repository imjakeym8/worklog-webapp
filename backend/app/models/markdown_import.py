from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.worklog import Worklog


class MarkdownImport(Base):
    """Provenance only; PostgreSQL Worklogs remain the authoritative records."""

    __tablename__ = "markdown_imports"
    __table_args__ = (UniqueConstraint("user_id", "source_key", name="uq_markdown_import_source"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    worklog_id: Mapped[UUID] = mapped_column(ForeignKey("worklogs.id", ondelete="CASCADE"))
    source_key: Mapped[str] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    worklog: Mapped[Worklog] = relationship(back_populates="markdown_imports")
    user: Mapped[User] = relationship()

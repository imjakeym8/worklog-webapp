from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.github_repository import GitHubRepository
    from app.models.worklog import Worklog


class MarkdownPublication(Base):
    __tablename__ = "markdown_publications"
    __table_args__ = (
        UniqueConstraint("worklog_id", "repository_id", "path", name="uq_markdown_publication"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    worklog_id: Mapped[UUID] = mapped_column(ForeignKey("worklogs.id", ondelete="CASCADE"))
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("github_repositories.id", ondelete="CASCADE")
    )
    path: Mapped[str] = mapped_column(String(500))
    last_published_file_sha: Mapped[str] = mapped_column(String(100))
    last_published_commit_sha: Mapped[str] = mapped_column(String(100))
    last_published_content_hash: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    worklog: Mapped[Worklog] = relationship()
    repository: Mapped[GitHubRepository] = relationship(back_populates="publications")

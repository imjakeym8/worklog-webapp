from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.markdown_publication import MarkdownPublication
    from app.models.user import User


class GitHubRepository(Base):
    __tablename__ = "github_repositories"
    __table_args__ = (
        UniqueConstraint("user_id", "github_repository_id", name="uq_github_repo_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    github_repository_id: Mapped[int] = mapped_column(BigInteger)
    github_installation_id: Mapped[int] = mapped_column(BigInteger)
    owner: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(201))
    default_branch: Mapped[str] = mapped_column(String(255))
    private: Mapped[bool] = mapped_column(Boolean)
    html_url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship()
    publications: Mapped[list[MarkdownPublication]] = relationship(back_populates="repository")

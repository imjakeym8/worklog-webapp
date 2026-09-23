from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.markdown_import import MarkdownImport
    from app.models.user import User

worklog_tracks = Table(
    "worklog_tracks",
    Base.metadata,
    Column("worklog_id", ForeignKey("worklogs.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_worklog_tracks_track_id", "track_id"),
)


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = (CheckConstraint("length(btrim(name)) > 0", name="ck_tracks_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    worklogs: Mapped[list[Worklog]] = relationship(
        secondary=worklog_tracks, back_populates="tracks", lazy="raise"
    )


class Worklog(Base):
    __tablename__ = "worklogs"
    __table_args__ = (
        CheckConstraint("hours > 0", name="ck_worklogs_hours_positive"),
        CheckConstraint("length(btrim(activity_breakdown)) > 0", name="ck_worklogs_activity"),
        CheckConstraint("cardinality(blockers) <= 50", name="ck_worklogs_blockers_count"),
        CheckConstraint("cardinality(next_steps) <= 50", name="ck_worklogs_next_count"),
        CheckConstraint("visibility IN ('public', 'private')", name="ck_worklogs_visibility"),
        Index("ix_worklogs_owner_chronology", "user_id", "date", "created_at", "id"),
        Index("ix_worklogs_public_chronology", "visibility", "date", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date)
    hours: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    shipped: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    visibility: Mapped[str] = mapped_column(String(7), server_default=text("'private'"))
    activity_breakdown: Mapped[str] = mapped_column(Text)
    detailed_notes: Mapped[str] = mapped_column(Text, server_default=text("''"))
    quick_summary: Mapped[str] = mapped_column(Text, server_default=text("''"))
    blockers: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    next: Mapped[list[str]] = mapped_column(
        "next_steps", ARRAY(Text), server_default=text("'{}'::text[]")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tracks: Mapped[list[Track]] = relationship(
        secondary=worklog_tracks,
        back_populates="worklogs",
        lazy="raise",
        order_by=Track.name,
        passive_deletes=True,
    )
    user: Mapped[User] = relationship(back_populates="worklogs")
    attachment: Mapped[Attachment | None] = relationship(
        back_populates="worklog", uselist=False, passive_deletes="all"
    )
    markdown_imports: Mapped[list[MarkdownImport]] = relationship(
        back_populates="worklog", passive_deletes=True
    )

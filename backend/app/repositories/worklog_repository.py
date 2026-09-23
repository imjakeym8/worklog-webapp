from __future__ import annotations

import base64
import binascii
import builtins
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import APIError
from app.models.worklog import Track, Worklog
from app.schemas.worklog import WorklogCreate, WorklogUpdate


class Cursor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    created_at: AwareDatetime
    id: UUID

    def encode(self) -> str:
        return base64.urlsafe_b64encode(self.model_dump_json().encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str) -> Cursor:
        try:
            data = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
            return cls.model_validate_json(data)
        except (ValueError, binascii.Error, ValidationError) as error:
            raise APIError(422, "INVALID_CURSOR", "The pagination cursor is invalid.") from error


class WorklogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, worklog_id: UUID, user_id: UUID, *, lock: bool = False) -> Worklog | None:
        statement = (
            select(Worklog)
            .where(Worklog.id == worklog_id, Worklog.user_id == user_id)
            .options(selectinload(Worklog.tracks), selectinload(Worklog.attachment))
        )
        if lock:
            statement = statement.with_for_update()
        return (await self.session.scalars(statement)).one_or_none()

    async def resolve_tracks(self, names: list[str]) -> list[Track]:
        if not names:
            return []
        # Stable insertion order avoids deadlocks when concurrent requests share labels.
        await self.session.execute(
            insert(Track)
            .values([{"id": uuid4(), "name": name} for name in sorted(set(names))])
            .on_conflict_do_nothing(index_elements=[Track.name])
        )
        return list(
            await self.session.scalars(
                select(Track).where(Track.name.in_(names)).order_by(Track.name)
            )
        )

    async def create(self, payload: WorklogCreate, user_id: UUID) -> Worklog:
        tracks = await self.resolve_tracks(payload.tracks)
        worklog = Worklog(**payload.model_dump(exclude={"tracks"}), user_id=user_id, tracks=tracks)
        self.session.add(worklog)
        await self.session.flush()
        return worklog

    async def update(self, worklog: Worklog, payload: WorklogUpdate) -> Worklog:
        values = payload.model_dump(exclude_unset=True, exclude={"tracks"})
        for name, value in values.items():
            setattr(worklog, name, value)
        if "tracks" in payload.model_fields_set:
            worklog.tracks = await self.resolve_tracks(payload.tracks or [])
        # Touch the parent even for association-only changes; the DB trigger sets the timestamp.
        worklog.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(worklog, attribute_names=["updated_at"])
        return worklog

    async def delete(self, worklog: Worklog) -> None:
        await self.session.delete(worklog)
        await self.session.flush()

    async def list(
        self,
        *,
        user_id: UUID,
        year: int | None,
        track: str | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[builtins.list[Worklog], str | None]:
        statement = (
            select(Worklog)
            .where(Worklog.user_id == user_id)
            .options(selectinload(Worklog.tracks), selectinload(Worklog.attachment))
        )
        if year is not None:
            statement = statement.where(Worklog.date.between(date(year, 1, 1), date(year, 12, 31)))
        if track is not None:
            statement = statement.where(Worklog.tracks.any(Track.name == track.strip()))
        if search and search.strip():
            term = search.strip()
            statement = statement.where(
                or_(
                    Worklog.activity_breakdown.icontains(term, autoescape=True),
                    Worklog.detailed_notes.icontains(term, autoescape=True),
                    Worklog.quick_summary.icontains(term, autoescape=True),
                    Worklog.tracks.any(Track.name.icontains(term, autoescape=True)),
                    func.array_to_string(Worklog.blockers, " ").icontains(term, autoescape=True),
                    func.array_to_string(Worklog.next, " ").icontains(term, autoescape=True),
                )
            )
        if cursor:
            position = Cursor.decode(cursor)
            statement = statement.where(
                tuple_(Worklog.date, Worklog.created_at, Worklog.id)
                < tuple_(literal(position.date), literal(position.created_at), literal(position.id))
            )
        statement = statement.order_by(
            Worklog.date.desc(), Worklog.created_at.desc(), Worklog.id.desc()
        ).limit(limit + 1)
        results = builtins.list(await self.session.scalars(statement))
        next_cursor = None
        if len(results) > limit:
            last = results[limit - 1]
            next_cursor = Cursor(date=last.date, created_at=last.created_at, id=last.id).encode()
        return results[:limit], next_cursor

    async def list_tracks(self, user_id: UUID) -> builtins.list[Track]:
        return list(
            await self.session.scalars(
                select(Track)
                .where(Track.worklogs.any(Worklog.user_id == user_id))
                .order_by(Track.name)
            )
        )

    async def get_public(self, worklog_id: UUID) -> Worklog | None:
        statement = (
            select(Worklog)
            .where(Worklog.id == worklog_id, Worklog.visibility == "public")
            .options(selectinload(Worklog.tracks), selectinload(Worklog.attachment))
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def list_public(
        self,
        *,
        year: int | None,
        track: str | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[builtins.list[Worklog], str | None]:
        statement = (
            select(Worklog)
            .where(Worklog.visibility == "public")
            .options(selectinload(Worklog.tracks), selectinload(Worklog.attachment))
        )
        if year is not None:
            statement = statement.where(Worklog.date.between(date(year, 1, 1), date(year, 12, 31)))
        if track is not None:
            statement = statement.where(Worklog.tracks.any(Track.name == track.strip()))
        if search and search.strip():
            term = search.strip()
            statement = statement.where(
                or_(
                    Worklog.activity_breakdown.icontains(term, autoescape=True),
                    Worklog.detailed_notes.icontains(term, autoescape=True),
                    Worklog.quick_summary.icontains(term, autoescape=True),
                    Worklog.tracks.any(Track.name.icontains(term, autoescape=True)),
                    func.array_to_string(Worklog.blockers, " ").icontains(term, autoescape=True),
                    func.array_to_string(Worklog.next, " ").icontains(term, autoescape=True),
                )
            )
        if cursor:
            position = Cursor.decode(cursor)
            statement = statement.where(
                tuple_(Worklog.date, Worklog.created_at, Worklog.id)
                < tuple_(literal(position.date), literal(position.created_at), literal(position.id))
            )
        statement = statement.order_by(
            Worklog.date.desc(), Worklog.created_at.desc(), Worklog.id.desc()
        ).limit(limit + 1)
        results = builtins.list(await self.session.scalars(statement))
        next_cursor = None
        if len(results) > limit:
            last = results[limit - 1]
            next_cursor = Cursor(date=last.date, created_at=last.created_at, id=last.id).encode()
        return results[:limit], next_cursor

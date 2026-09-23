import builtins
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.storage import ImageStorage, StorageOperationError
from app.models.worklog import Worklog
from app.repositories.worklog_repository import WorklogRepository
from app.schemas.worklog import (
    TrackResponse,
    WorklogCreate,
    WorklogListResponse,
    WorklogResponse,
    WorklogUpdate,
)
from app.services.attachment_serialization import serialize_attachment


def serialize_worklog(worklog: Worklog) -> WorklogResponse:
    attachment = worklog.__dict__.get("attachment")
    return WorklogResponse(
        id=worklog.id,
        date=worklog.date,
        hours=worklog.hours,
        shipped=worklog.shipped,
        visibility=worklog.visibility,
        tracks=[track.name for track in worklog.tracks],
        blockers=worklog.blockers,
        next=worklog.next,
        activity_breakdown=worklog.activity_breakdown,
        detailed_notes=worklog.detailed_notes,
        quick_summary=worklog.quick_summary,
        attachment=serialize_attachment(attachment) if attachment else None,
        created_at=worklog.created_at,
        updated_at=worklog.updated_at,
    )


class WorklogService:
    def __init__(self, session: AsyncSession, user_id: UUID, storage: ImageStorage) -> None:
        self.session = session
        self.user_id = user_id
        self.storage = storage
        self.repository = WorklogRepository(session)

    async def require_worklog(self, worklog_id: UUID, *, lock: bool = False) -> Worklog:
        worklog = await self.repository.get(worklog_id, self.user_id, lock=lock)
        if worklog is None:
            raise APIError(404, "WORKLOG_NOT_FOUND", "The requested worklog does not exist.")
        return worklog

    async def create(self, payload: WorklogCreate, *, commit: bool = True) -> WorklogResponse:
        response = serialize_worklog(await self.repository.create(payload, self.user_id))
        if commit:
            await self.session.commit()
        return response

    async def get(self, worklog_id: UUID) -> WorklogResponse:
        return serialize_worklog(await self.require_worklog(worklog_id))

    async def update(
        self, worklog_id: UUID, payload: WorklogUpdate, *, commit: bool = True
    ) -> WorklogResponse:
        worklog = await self.require_worklog(worklog_id, lock=True)
        response = serialize_worklog(await self.repository.update(worklog, payload))
        if commit:
            await self.session.commit()
        return response

    async def delete(self, worklog_id: UUID) -> None:
        worklog = await self.require_worklog(worklog_id, lock=True)
        if worklog.attachment is not None:
            storage_keys = [worklog.attachment.storage_key]
            if worklog.attachment.pending_delete_storage_key:
                storage_keys.append(worklog.attachment.pending_delete_storage_key)
            try:
                for storage_key in storage_keys:
                    await self.storage.delete_image(storage_key)
            except StorageOperationError as error:
                raise APIError(
                    503, "ATTACHMENT_DELETE_FAILED", "The image could not be removed."
                ) from error
        await self.repository.delete(worklog)
        await self.session.commit()

    async def list(
        self,
        *,
        year: int | None,
        track: str | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> WorklogListResponse:
        worklogs, next_cursor = await self.repository.list(
            user_id=self.user_id,
            year=year,
            track=track,
            search=search,
            limit=limit,
            cursor=cursor,
        )
        return WorklogListResponse(
            items=[serialize_worklog(worklog) for worklog in worklogs], next_cursor=next_cursor
        )

    async def list_tracks(self) -> builtins.list[TrackResponse]:
        return [
            TrackResponse(id=track.id, name=track.name)
            for track in await self.repository.list_tracks(self.user_id)
        ]

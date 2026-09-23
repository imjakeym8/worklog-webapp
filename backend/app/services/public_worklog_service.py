from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.storage import ImageStorage, StorageOperationError
from app.models.user import User
from app.models.worklog import Worklog
from app.repositories.worklog_repository import WorklogRepository
from app.schemas.worklog import (
    PublicAttachmentResponse,
    PublicWorklogListResponse,
    PublicWorklogResponse,
)


def serialize_public_worklog(worklog: Worklog) -> PublicWorklogResponse:
    attachment = worklog.__dict__.get("attachment")
    return PublicWorklogResponse(
        id=worklog.id,
        date=worklog.date,
        hours=worklog.hours,
        shipped=worklog.shipped,
        tracks=[track.name for track in worklog.tracks],
        blockers=worklog.blockers,
        next=worklog.next,
        activity_breakdown=worklog.activity_breakdown,
        detailed_notes=worklog.detailed_notes,
        quick_summary=worklog.quick_summary,
        attachment=(
            PublicAttachmentResponse(original_filename=attachment.original_filename)
            if attachment is not None
            else None
        ),
    )


class PublicWorklogService:
    def __init__(self, session: AsyncSession, storage: ImageStorage) -> None:
        self.session = session
        self.storage = storage
        self.repository = WorklogRepository(session)

    async def list(
        self,
        *,
        year: int | None,
        track: str | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> PublicWorklogListResponse:
        worklogs, next_cursor = await self.repository.list_public(
            year=year, track=track, search=search, limit=limit, cursor=cursor
        )
        return PublicWorklogListResponse(
            items=[serialize_public_worklog(worklog) for worklog in worklogs],
            next_cursor=next_cursor,
        )

    async def get(self, worklog_id: UUID) -> PublicWorklogResponse:
        return serialize_public_worklog(await self._require_public_worklog(worklog_id))

    async def attachment_content(self, worklog_id: UUID) -> tuple[str, bytes]:
        # Storage stays private; a public URL is issued only after visibility is verified.
        worklog = await self._require_public_worklog(worklog_id)
        if worklog.attachment is None:
            raise APIError(404, "ATTACHMENT_NOT_FOUND", "The image attachment does not exist.")
        try:
            content = await self.storage.get_image(worklog.attachment.storage_key)
        except StorageOperationError as error:
            raise APIError(
                503,
                "ATTACHMENT_RETRIEVAL_FAILED",
                "The image is unavailable. Try again later.",
            ) from error
        return worklog.attachment.content_type, content

    async def profile(self) -> User | None:
        statement = (
            select(User)
            .join(Worklog)
            .where(Worklog.visibility == "public")
            .order_by(Worklog.updated_at.desc())
            .limit(1)
        )
        return cast(User | None, await self.session.scalar(statement))

    async def _require_public_worklog(self, worklog_id: UUID) -> Worklog:
        worklog = await self.repository.get_public(worklog_id)
        if worklog is None:
            raise APIError(404, "WORKLOG_NOT_FOUND", "The requested worklog does not exist.")
        return worklog

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import Response as RawResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import AdminUser, MutationOrigin
from app.core.storage import ImageStorage
from app.schemas.attachment import AttachmentResponse
from app.schemas.worklog import (
    TrackResponse,
    WorklogCreate,
    WorklogListResponse,
    WorklogResponse,
    WorklogUpdate,
)
from app.services.attachment_service import AttachmentService
from app.services.worklog_service import WorklogService

router = APIRouter(prefix="/api", tags=["worklogs"])


def get_authenticated_service(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)], user: AdminUser
) -> WorklogService:
    storage: ImageStorage = request.app.state.image_storage
    return WorklogService(session, user.id, storage)


Service = Annotated[WorklogService, Depends(get_authenticated_service)]


def get_attachment_service(service: Service) -> AttachmentService:
    return AttachmentService(service.session, service, service.storage)


AttachmentActions = Annotated[AttachmentService, Depends(get_attachment_service)]


@router.post("/worklogs", response_model=WorklogResponse, status_code=201)
async def create_worklog(
    payload: WorklogCreate, service: Service, origin: MutationOrigin
) -> WorklogResponse:
    return await service.create(payload)


@router.get("/worklogs", response_model=WorklogListResponse)
async def list_worklogs(
    service: Service,
    year: Annotated[int | None, Query(ge=1, le=9999)] = None,
    track: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(min_length=1, max_length=1024)] = None,
) -> WorklogListResponse:
    return await service.list(year=year, track=track, search=search, limit=limit, cursor=cursor)


@router.get("/worklogs/{worklog_id}", response_model=WorklogResponse)
async def get_worklog(worklog_id: UUID, service: Service) -> WorklogResponse:
    return await service.get(worklog_id)


@router.patch("/worklogs/{worklog_id}", response_model=WorklogResponse)
async def update_worklog(
    worklog_id: UUID, payload: WorklogUpdate, service: Service, origin: MutationOrigin
) -> WorklogResponse:
    return await service.update(worklog_id, payload)


@router.delete("/worklogs/{worklog_id}", status_code=204)
async def delete_worklog(worklog_id: UUID, service: Service, origin: MutationOrigin) -> Response:
    await service.delete(worklog_id)
    return Response(status_code=204)


@router.post(
    "/worklogs/{worklog_id}/attachment", response_model=AttachmentResponse, status_code=201
)
async def create_attachment(
    worklog_id: UUID,
    upload: Annotated[UploadFile, File(...)],
    attachments: AttachmentActions,
    origin: MutationOrigin,
) -> AttachmentResponse:
    return await attachments.create(worklog_id, upload)


@router.put("/worklogs/{worklog_id}/attachment", response_model=AttachmentResponse)
async def replace_attachment(
    worklog_id: UUID,
    upload: Annotated[UploadFile, File(...)],
    attachments: AttachmentActions,
    origin: MutationOrigin,
) -> AttachmentResponse:
    return await attachments.replace(worklog_id, upload)


@router.get("/worklogs/{worklog_id}/attachment")
async def get_attachment(worklog_id: UUID, attachments: AttachmentActions) -> RawResponse:
    attachment, content = await attachments.get_content(worklog_id)
    return RawResponse(
        content=content,
        media_type=attachment.content_type,
        headers={"Content-Disposition": "inline"},
    )


@router.delete("/worklogs/{worklog_id}/attachment", status_code=204)
async def delete_attachment(
    worklog_id: UUID, attachments: AttachmentActions, origin: MutationOrigin
) -> Response:
    await attachments.delete(worklog_id)
    return Response(status_code=204)


@router.get("/tracks", response_model=list[TrackResponse])
async def list_tracks(service: Service) -> list[TrackResponse]:
    return await service.list_tracks()

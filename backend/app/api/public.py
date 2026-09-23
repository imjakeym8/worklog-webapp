from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.storage import ImageStorage
from app.schemas.worklog import PublicWorklogListResponse, PublicWorklogResponse
from app.services.public_worklog_service import PublicWorklogService

router = APIRouter(prefix="/api/public", tags=["public worklogs"])


class PublicProfileResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda name: "".join(
            word if index == 0 else word.capitalize() for index, word in enumerate(name.split("_"))
        ),
        populate_by_name=True,
    )

    github_login: str
    github_avatar_url: str | None
    github_profile_url: str


def get_public_service(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> PublicWorklogService:
    storage: ImageStorage = request.app.state.image_storage
    return PublicWorklogService(session, storage)


Service = Annotated[PublicWorklogService, Depends(get_public_service)]


@router.get("/worklogs", response_model=PublicWorklogListResponse)
async def list_public_worklogs(
    service: Service,
    year: Annotated[int | None, Query(ge=1, le=9999)] = None,
    track: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    search: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(min_length=1, max_length=1024)] = None,
) -> PublicWorklogListResponse:
    return await service.list(year=year, track=track, search=search, limit=limit, cursor=cursor)


@router.get("/worklogs/{worklog_id}", response_model=PublicWorklogResponse)
async def get_public_worklog(worklog_id: UUID, service: Service) -> PublicWorklogResponse:
    return await service.get(worklog_id)


@router.get("/worklogs/{worklog_id}/attachment")
async def get_public_attachment(worklog_id: UUID, service: Service) -> Response:
    content_type, content = await service.attachment_content(worklog_id)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": "inline"},
    )


@router.get("/profile", response_model=PublicProfileResponse | None)
async def get_public_profile(service: Service) -> PublicProfileResponse | None:
    user = await service.profile()
    if user is None:
        return None
    return PublicProfileResponse(
        github_login=user.github_login,
        github_avatar_url=user.avatar_url,
        github_profile_url=f"https://github.com/{user.github_login}",
    )

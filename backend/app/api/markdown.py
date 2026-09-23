from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response

from app.api.worklogs import Service
from app.core.errors import APIError
from app.core.security import MutationOrigin
from app.integrations.github_client import GitHubAppClient
from app.schemas.github import MarkdownPublishRequest, MarkdownPublishResponse
from app.schemas.worklog import WorklogResponse
from app.services.github_publish_service import GitHubRepositoryService, MarkdownPublishService
from app.services.markdown_portability_service import (
    MarkdownPortabilityService,
    export_worklog_markdown,
)

router = APIRouter(prefix="/api", tags=["markdown"])


@router.get("/worklogs/{worklog_id}/markdown")
async def export_markdown(worklog_id: UUID, service: Service) -> Response:
    worklog = await service.get(worklog_id)
    return Response(
        export_worklog_markdown(worklog),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="worklog-{worklog.date.isoformat()}.md"'
        },
    )


@router.post("/imports/markdown", response_model=WorklogResponse, status_code=201)
async def import_markdown(
    service: Service,
    origin: MutationOrigin,
    upload: Annotated[UploadFile, File(...)],
    update: Annotated[bool, Form()] = False,
) -> WorklogResponse:
    if not upload.filename or not upload.filename.lower().endswith(".md"):
        raise APIError(422, "MARKDOWN_FILE_INVALID", "Choose a single .md file.")
    content = await upload.read(1_000_001)
    return await MarkdownPortabilityService(service.session, service).import_content(
        content, f"local:{upload.filename}", update=update
    )


@router.post("/worklogs/{worklog_id}/publish", response_model=MarkdownPublishResponse)
async def publish_markdown(
    worklog_id: UUID,
    payload: MarkdownPublishRequest,
    request: Request,
    service: Service,
    origin: MutationOrigin,
) -> MarkdownPublishResponse:
    repositories = GitHubRepositoryService(
        service.session, service.user_id, GitHubAppClient(request.app.state.settings)
    )
    return await MarkdownPublishService(service.session, service, repositories).publish(
        worklog_id, payload
    )

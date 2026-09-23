from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import AdminUser, MutationOrigin
from app.integrations.github_client import GitHubAppClient
from app.models.github_repository import GitHubRepository
from app.schemas.github import (
    GitHubAvailableRepository,
    GitHubRepositoryConnect,
    GitHubRepositoryResponse,
)
from app.services.github_publish_service import GitHubRepositoryService

router = APIRouter(prefix="/api/github", tags=["github"])


def service(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)], user: AdminUser
) -> GitHubRepositoryService:
    return GitHubRepositoryService(session, user.id, GitHubAppClient(request.app.state.settings))


RepositoryService = Annotated[GitHubRepositoryService, Depends(service)]


def response(repository: GitHubRepository) -> GitHubRepositoryResponse:
    return GitHubRepositoryResponse(
        id=repository.id,
        full_name=repository.full_name,
        private=repository.private,
        html_url=repository.html_url,
        default_branch=repository.default_branch,
    )


@router.get("/repositories", response_model=list[GitHubRepositoryResponse])
async def repositories(repositories: RepositoryService) -> list[GitHubRepositoryResponse]:
    return [response(item) for item in await repositories.list_connected()]


@router.get("/available-repositories", response_model=list[GitHubAvailableRepository])
async def available_repositories(
    user: AdminUser, repositories: RepositoryService
) -> list[GitHubAvailableRepository]:
    return [
        GitHubAvailableRepository(
            github_repository_id=item.repository_id,
            installation_id=item.installation_id,
            full_name=item.full_name,
            private=item.private,
        )
        for item in await repositories.client.list_available_repositories(user.github_login)
    ]


@router.post("/repositories/connect", response_model=GitHubRepositoryResponse, status_code=201)
async def connect_repository(
    payload: GitHubRepositoryConnect,
    user: AdminUser,
    repositories: RepositoryService,
    origin: MutationOrigin,
) -> GitHubRepositoryResponse:
    return response(await repositories.connect(user.github_login, payload.github_repository_id))

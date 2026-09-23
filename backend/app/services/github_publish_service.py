from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.integrations.github_client import GitHubAppClient, GitHubRepositoryData
from app.models.github_repository import GitHubRepository
from app.models.markdown_publication import MarkdownPublication
from app.schemas.github import MarkdownPublishRequest, MarkdownPublishResponse
from app.services.markdown_portability_service import export_worklog_markdown
from app.services.worklog_service import WorklogService


def validate_repository_path(value: str) -> str:
    path = value.replace("\\", "/").strip()
    if not path or "\x00" in path or path.startswith("/"):
        raise APIError(422, "GITHUB_PATH_INVALID", "Choose a repository-relative Markdown path.")
    parsed = PurePosixPath(path)
    if any(part in {"", ".", ".."} for part in parsed.parts) or not path.lower().endswith(".md"):
        raise APIError(422, "GITHUB_PATH_INVALID", "Choose a safe repository-relative .md path.")
    return str(parsed)


def repository_data(repository: GitHubRepository) -> GitHubRepositoryData:
    return GitHubRepositoryData(
        repository.github_repository_id,
        repository.github_installation_id,
        repository.owner,
        repository.name,
        repository.full_name,
        repository.default_branch,
        repository.private,
        repository.html_url,
    )


class GitHubRepositoryService:
    def __init__(self, session: AsyncSession, user_id: UUID, client: GitHubAppClient) -> None:
        self.session = session
        self.user_id = user_id
        self.client = client

    async def list_connected(self) -> list[GitHubRepository]:
        return list(
            await self.session.scalars(
                select(GitHubRepository)
                .where(GitHubRepository.user_id == self.user_id)
                .order_by(GitHubRepository.full_name)
            )
        )

    async def connect(self, github_login: str, github_repository_id: int) -> GitHubRepository:
        available = await self.client.list_available_repositories(github_login)
        selected = next(
            (item for item in available if item.repository_id == github_repository_id), None
        )
        if selected is None:
            raise APIError(
                403,
                "GITHUB_REPOSITORY_NOT_AVAILABLE",
                "That repository is not available to your GitHub App installation.",
            )
        repository = await self.session.scalar(
            select(GitHubRepository).where(
                GitHubRepository.user_id == self.user_id,
                GitHubRepository.github_repository_id == selected.repository_id,
            )
        )
        if repository is None:
            repository = GitHubRepository(
                user_id=self.user_id,
                github_repository_id=selected.repository_id,
                github_installation_id=selected.installation_id,
                owner=selected.owner,
                name=selected.name,
                full_name=selected.full_name,
                default_branch=selected.default_branch,
                private=selected.private,
                html_url=selected.html_url,
            )
            self.session.add(repository)
        else:
            repository.github_installation_id = selected.installation_id
            repository.owner, repository.name, repository.full_name = (
                selected.owner,
                selected.name,
                selected.full_name,
            )
            repository.default_branch, repository.private, repository.html_url = (
                selected.default_branch,
                selected.private,
                selected.html_url,
            )
        await self.session.flush()
        return repository

    async def require_owned(self, repository_id: UUID) -> GitHubRepository:
        repository = await self.session.scalar(
            select(GitHubRepository).where(
                GitHubRepository.id == repository_id, GitHubRepository.user_id == self.user_id
            )
        )
        if repository is None:
            raise APIError(
                404, "GITHUB_REPOSITORY_NOT_FOUND", "The requested repository is not connected."
            )
        return repository


class MarkdownPublishService:
    def __init__(
        self, session: AsyncSession, worklogs: WorklogService, repositories: GitHubRepositoryService
    ) -> None:
        self.session, self.worklogs, self.repositories = session, worklogs, repositories

    async def publish(
        self, worklog_id: UUID, request: MarkdownPublishRequest
    ) -> MarkdownPublishResponse:
        path = validate_repository_path(request.path)
        worklog = await self.worklogs.get(worklog_id)
        repository = await self.repositories.require_owned(request.repository_id)
        markdown = export_worklog_markdown(worklog).encode()
        content_hash = hashlib.sha256(markdown).hexdigest()
        publication = await self.session.scalar(
            select(MarkdownPublication).where(
                MarkdownPublication.worklog_id == worklog_id,
                MarkdownPublication.repository_id == repository.id,
                MarkdownPublication.path == path,
            )
        )
        if publication and publication.last_published_content_hash == content_hash:
            return MarkdownPublishResponse(
                status="up_to_date", path=path, published_at=publication.published_at
            )
        remote = await self.repositories.client.get_file(repository_data(repository), path)
        if publication is None and remote is not None:
            raise APIError(
                409,
                "GITHUB_PUBLISH_PATH_EXISTS",
                "A file already exists at this path and is not linked to this Worklog.",
            )
        if publication is not None and (
            remote is None or remote.sha != publication.last_published_file_sha
        ):
            raise APIError(
                409,
                "GITHUB_PUBLISH_CONFLICT",
                "The GitHub file has changed since the last publish.",
            )
        result = await self.repositories.client.put_file(
            repository_data(repository),
            path,
            markdown,
            request.commit_message.strip(),
            remote.sha if remote else None,
        )
        now = datetime.now(UTC)
        if publication is None:
            publication = MarkdownPublication(
                worklog_id=worklog_id,
                repository_id=repository.id,
                path=path,
                last_published_file_sha=result.file_sha,
                last_published_commit_sha=result.commit_sha,
                last_published_content_hash=content_hash,
            )
            self.session.add(publication)
        else:
            publication.last_published_file_sha, publication.last_published_commit_sha = (
                result.file_sha,
                result.commit_sha,
            )
            publication.last_published_content_hash, publication.published_at = content_hash, now
        await self.session.flush()
        return MarkdownPublishResponse(
            status="published",
            path=path,
            commit_sha=result.commit_sha,
            html_url=result.html_url,
            published_at=now,
        )

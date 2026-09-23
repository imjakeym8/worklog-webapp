from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.worklog import APIModel


class GitHubRepositoryResponse(APIModel):
    id: UUID
    full_name: str
    private: bool
    html_url: str
    default_branch: str


class GitHubAvailableRepository(APIModel):
    github_repository_id: int
    installation_id: int
    full_name: str
    private: bool


class GitHubRepositoryConnect(APIModel):
    github_repository_id: int


class MarkdownPublishRequest(APIModel):
    repository_id: UUID
    path: str = Field(min_length=1, max_length=500)
    commit_message: str = Field(min_length=1, max_length=250)


class MarkdownPublishResponse(APIModel):
    status: str
    path: str
    commit_sha: str | None = None
    html_url: str | None = None
    published_at: datetime | None = None

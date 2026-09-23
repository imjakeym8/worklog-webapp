from typing import Protocol, cast

import httpx
from authlib.integrations.starlette_client import OAuth  # type: ignore[import-untyped]
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.schemas.auth import GitHubIdentity


class GitHubOAuthClient(Protocol):
    async def authorize_redirect(self, request: Request) -> Response: ...

    async def fetch_identity(self, request: Request) -> GitHubIdentity: ...


class AuthlibRemoteClient(Protocol):
    async def authorize_redirect(self, request: Request, redirect_uri: str) -> Response: ...

    async def authorize_access_token(self, request: Request) -> dict[str, object]: ...

    async def get(self, url: str, *, token: dict[str, object]) -> httpx.Response: ...


class AuthlibGitHubOAuthClient:
    def __init__(self, settings: Settings) -> None:
        oauth = OAuth()
        self.client = cast(
            AuthlibRemoteClient,
            oauth.register(
                name="github",
                client_id=settings.github_client_id,
                client_secret=settings.github_client_secret.get_secret_value(),
                access_token_url="https://github.com/login/oauth/access_token",
                authorize_url="https://github.com/login/oauth/authorize",
                api_base_url="https://api.github.com/",
                client_kwargs={
                    "code_challenge_method": "S256",
                    "headers": {"Accept": "application/vnd.github+json"},
                },
            ),
        )
        self.callback_url = str(settings.github_callback_url)

    async def authorize_redirect(self, request: Request) -> Response:
        return await self.client.authorize_redirect(request, self.callback_url)

    async def fetch_identity(self, request: Request) -> GitHubIdentity:
        token = await self.client.authorize_access_token(request)
        response = await self.client.get("user", token=token)
        response.raise_for_status()
        return GitHubIdentity.model_validate(response.json())

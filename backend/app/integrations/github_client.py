from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from authlib.jose import jwt  # type: ignore[import-untyped]

from app.core.config import Settings
from app.core.errors import APIError


@dataclass(frozen=True)
class GitHubRepositoryData:
    repository_id: int
    installation_id: int
    owner: str
    name: str
    full_name: str
    default_branch: str
    private: bool
    html_url: str


@dataclass(frozen=True)
class GitHubFile:
    sha: str
    content: bytes
    html_url: str


@dataclass(frozen=True)
class GitHubWriteResult:
    file_sha: str
    commit_sha: str
    html_url: str


class GitHubAppClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_app_jwt(self) -> str:
        if not self.settings.github_app_is_configured:
            raise APIError(
                503, "GITHUB_APP_NOT_CONFIGURED", "GitHub repository access is not configured."
            )
        now = int(time.time())
        claims = {"iat": now - 60, "exp": now + 540, "iss": self.settings.github_app_id}
        # .env files commonly store PEM newlines as literal \n characters.
        key = self.settings.github_app_private_key.get_secret_value().replace("\\n", "\n")  # type: ignore[union-attr]
        try:
            return str(jwt.encode({"alg": "RS256"}, claims, key).decode())
        except ValueError as error:
            raise APIError(
                503,
                "GITHUB_APP_PRIVATE_KEY_INVALID",
                "GitHub repository access is not configured correctly.",
            ) from error

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json: object | None = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            async with httpx.AsyncClient(base_url="https://api.github.com", timeout=15) as client:
                response = await client.request(method, path, headers=headers, json=json)
        except httpx.HTTPError as error:
            raise APIError(503, "GITHUB_API_UNAVAILABLE", "GitHub could not be reached.") from error
        if response.status_code == 429 or response.headers.get("x-ratelimit-remaining") == "0":
            raise APIError(
                429, "GITHUB_RATE_LIMITED", "GitHub rate limit reached. Try again later."
            )
        if response.status_code in {401, 403}:
            raise APIError(403, "GITHUB_ACCESS_DENIED", "GitHub denied repository access.")
        if response.status_code == 404 and allow_not_found:
            return response
        if response.status_code >= 400:
            raise APIError(502, "GITHUB_API_ERROR", "GitHub could not complete the request.")
        return response

    async def create_installation_token(self, installation_id: int) -> str:
        response = await self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            token=self.generate_app_jwt(),
        )
        token = response.json().get("token")
        if not isinstance(token, str):
            raise APIError(
                502, "GITHUB_API_ERROR", "GitHub returned an invalid installation token."
            )
        return token

    async def list_available_repositories(self, github_login: str) -> list[GitHubRepositoryData]:
        response = await self._request(
            "GET", "/app/installations?per_page=100", token=self.generate_app_jwt()
        )
        installations = response.json()
        if not isinstance(installations, list):
            raise APIError(502, "GITHUB_API_ERROR", "GitHub returned invalid installation data.")
        repositories: list[GitHubRepositoryData] = []
        for installation in installations:
            account = installation.get("account", {})
            if account.get("login", "").casefold() != github_login.casefold():
                continue
            installation_id = installation.get("id")
            if not isinstance(installation_id, int):
                continue
            token = await self.create_installation_token(installation_id)
            page = await self._request(
                "GET", "/installation/repositories?per_page=100", token=token
            )
            for repository in page.json().get("repositories", []):
                parsed = self._repository_data(repository, installation_id)
                if parsed:
                    repositories.append(parsed)
        return repositories

    async def get_file(self, repository: GitHubRepositoryData, path: str) -> GitHubFile | None:
        token = await self.create_installation_token(repository.installation_id)
        encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
        response = await self._request(
            "GET",
            f"/repos/{repository.full_name}/contents/{encoded_path}",
            token=token,
            allow_not_found=True,
        )
        if response.status_code == 404:
            return None
        data = response.json()
        content = data.get("content", "")
        if not isinstance(content, str) or not isinstance(data.get("sha"), str):
            raise APIError(502, "GITHUB_API_ERROR", "GitHub returned invalid file data.")
        return GitHubFile(data["sha"], base64.b64decode(content), str(data.get("html_url", "")))

    async def put_file(
        self,
        repository: GitHubRepositoryData,
        path: str,
        content: bytes,
        message: str,
        sha: str | None,
    ) -> GitHubWriteResult:
        token = await self.create_installation_token(repository.installation_id)
        payload: dict[str, str] = {
            "message": message,
            "content": base64.b64encode(content).decode(),
        }
        if sha:
            payload["sha"] = sha
        response = await self._request(
            "PUT", f"/repos/{repository.full_name}/contents/{path}", token=token, json=payload
        )
        data: dict[str, Any] = response.json()
        return GitHubWriteResult(
            str(data["content"]["sha"]),
            str(data["commit"]["sha"]),
            str(data["content"].get("html_url", "")),
        )

    @staticmethod
    def _repository_data(data: object, installation_id: int) -> GitHubRepositoryData | None:
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("id"), int)
            or not isinstance(data.get("full_name"), str)
        ):
            return None
        owner = data.get("owner", {}).get("login")
        name = data.get("name")
        if not isinstance(owner, str) or not isinstance(name, str):
            return None
        return GitHubRepositoryData(
            data["id"],
            installation_id,
            owner,
            name,
            data["full_name"],
            str(data.get("default_branch", "main")),
            bool(data.get("private", True)),
            str(data.get("html_url", "")),
        )

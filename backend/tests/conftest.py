import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request
from starlette.responses import RedirectResponse

from alembic import command
from app.api.auth import get_github_oauth
from app.core.config import Settings
from app.core.database import get_session
from app.core.storage import StorageOperationError
from app.main import create_app
from app.schemas.auth import GitHubIdentity

TEST_SECRET = "test-secret-value-that-is-at-least-32-characters"
DEFAULT_IDENTITY = GitHubIdentity(
    id=1001,
    login="first-user",
    name="First User",
    avatar_url="https://avatars.githubusercontent.com/u/1001",
    email=None,
)


class FakeGitHubOAuthClient:
    def __init__(self) -> None:
        self.identity = DEFAULT_IDENTITY

    async def authorize_redirect(self, request: Request) -> RedirectResponse:
        return RedirectResponse("https://github.com/login/oauth/authorize?state=fake")

    async def fetch_identity(self, request: Request) -> GitHubIdentity:
        return self.identity


class FakeImageStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.saved_keys: list[str] = []
        self.deleted_keys: list[str] = []
        self.fail_save = False
        self.fail_delete = False

    async def save_image(self, storage_key: str, content: bytes, content_type: str) -> None:
        if self.fail_save:
            raise StorageOperationError("save failed")
        self.objects[storage_key] = content
        self.saved_keys.append(storage_key)

    async def get_image(self, storage_key: str) -> bytes:
        try:
            return self.objects[storage_key]
        except KeyError as error:
            raise StorageOperationError("missing object") from error

    async def delete_image(self, storage_key: str) -> None:
        if self.fail_delete:
            raise StorageOperationError("delete failed")
        self.objects.pop(storage_key, None)
        self.deleted_keys.append(storage_key)


@dataclass
class TestContext:
    __test__ = False

    http: AsyncClient
    app: FastAPI
    oauth: FakeGitHubOAuthClient
    storage: FakeImageStorage
    session_factory: async_sessionmaker[AsyncSession]

    async def login(self, identity: GitHubIdentity = DEFAULT_IDENTITY) -> Response:
        self.oauth.identity = identity
        response = await self.http.get("/api/auth/github/callback?code=fake&state=fake")
        assert response.status_code == 303, response.text
        return response


@pytest.fixture
async def test_context() -> AsyncIterator[TestContext]:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    settings = Settings(
        database_url=database_url,
        environment="test",
        backend_url="http://test",
        github_client_id="test-client-id",
        github_client_secret=TEST_SECRET,
        github_callback_url="http://test/api/auth/github/callback",
        session_secret=TEST_SECRET,
        admin_github_logins="first-user,owner-one,owner-two,imjakeym8,markschwart34",
        _env_file=None,
    )
    schema = "worklog_test_" + uuid4().hex
    admin = create_async_engine(settings.database_url.get_secret_value(), poolclass=NullPool)
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        async with engine.begin() as connection:

            def migrate(sync_connection) -> None:
                config.attributes["connection"] = sync_connection
                command.upgrade(config, "head")

            await connection.run_sync(migrate)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def test_session() -> AsyncIterator[AsyncSession]:
            async with factory() as session, session.begin():
                yield session

        app = create_app(settings)
        oauth = FakeGitHubOAuthClient()
        storage = FakeImageStorage()
        app.dependency_overrides[get_session] = test_session
        app.dependency_overrides[get_github_oauth] = lambda: oauth
        app.state.image_storage = storage
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"Origin": "http://localhost:3000"},
            ) as http:
                yield TestContext(http, app, oauth, storage, factory)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.fixture
async def client(test_context: TestContext) -> AsyncClient:
    await test_context.login()
    return test_context.http

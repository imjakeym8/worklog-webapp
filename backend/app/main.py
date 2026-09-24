import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.github import router as github_router
from app.api.markdown import router as markdown_router
from app.api.public import router as public_router
from app.api.worklogs import router
from app.core.config import Settings
from app.core.database import create_engine
from app.core.errors import APIError
from app.core.oauth import AuthlibGitHubOAuthClient
from app.core.storage import create_image_storage

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Worklog API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.github_oauth = AuthlibGitHubOAuthClient(settings)
    app.state.image_storage = create_image_storage(settings)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret.get_secret_value(),
        session_cookie="worklog_session",
        max_age=settings.session_max_age_seconds,
        path="/api",
        same_site="lax",
        https_only=settings.environment == "production",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.frontend_url).rstrip("/")],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=True,
    )
    app.include_router(auth_router)
    app.include_router(public_router)
    app.include_router(router)
    app.include_router(markdown_router)
    app.include_router(github_router)

    @app.get("/api/health", tags=["health"])
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, error: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request contains invalid values.",
                    "details": [
                        {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
                        for item in error.errors()
                    ],
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def handle_http(request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": str(error.detail)}},
            headers=error.headers,
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity(request: Request, error: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "DATA_CONFLICT",
                    "message": "The change conflicts with stored data.",
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database(request: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.error("Database request failed (%s)", type(error).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "The database is unavailable. Try again later.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        logger.error("Unexpected request failure (%s)", type(error).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The request could not be completed.",
                }
            },
        )

    return app

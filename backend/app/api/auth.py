import logging
from typing import Annotated, cast

import httpx
from authlib.integrations.base_client import OAuthError  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.oauth import GitHubOAuthClient
from app.core.security import CurrentUser, MutationOrigin
from app.repositories.user_repository import UserRepository
from app.schemas.auth import CurrentUserResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


def get_github_oauth(request: Request) -> GitHubOAuthClient:
    return cast(GitHubOAuthClient, request.app.state.github_oauth)


OAuthClient = Annotated[GitHubOAuthClient, Depends(get_github_oauth)]
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/github")
async def start_github_login(request: Request, oauth: OAuthClient) -> Response:
    # Clearing an existing session prevents a login from inheriting an old authenticated identity.
    request.session.clear()
    if request.query_params.get("next") in {"/admin", "/worklog/admin"}:
        request.session["redirect_after_login"] = "/admin"
    return await oauth.authorize_redirect(request)


@router.get("/github/callback")
async def github_callback(
    request: Request, oauth: OAuthClient, session: Session
) -> RedirectResponse:
    frontend_url = str(request.app.state.settings.frontend_url).rstrip("/")
    redirect_after_login = request.session.get("redirect_after_login")
    try:
        identity = await oauth.fetch_identity(request)
        user = await UserRepository(session).upsert_github_user(identity)
        await session.commit()
    except (OAuthError, httpx.HTTPError, ValidationError, SQLAlchemyError) as error:
        await session.rollback()
        request.session.clear()
        logger.warning("GitHub authentication failed (%s)", type(error).__name__)
        return RedirectResponse(f"{frontend_url}/?auth=failed", status_code=303)

    # Replace all temporary OAuth state with the minimal local application session.
    request.session.clear()
    request.session["user_id"] = str(user.id)
    destination = redirect_after_login or "/admin"
    return RedirectResponse(f"{frontend_url}{destination}", status_code=303)


@router.get("/me", response_model=CurrentUserResponse, response_model_by_alias=True)
async def current_user(request: Request, user: CurrentUser) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=str(user.id),
        github_login=user.github_login,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_admin=user.github_login.casefold() in request.app.state.settings.allowed_admin_logins,
    )


@router.post("/logout", status_code=204)
async def logout(request: Request, origin: MutationOrigin) -> Response:
    request.session.clear()
    return Response(status_code=204)

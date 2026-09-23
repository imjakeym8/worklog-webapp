from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import APIError
from app.models.user import User


def require_same_origin(request: Request) -> None:
    expected_origin = str(request.app.state.settings.frontend_url).rstrip("/")
    if request.headers.get("origin") != expected_origin:
        raise APIError(403, "INVALID_ORIGIN", "The request origin is not allowed.")


async def get_current_user(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    raw_user_id = request.session.get("user_id")
    try:
        user_id = UUID(raw_user_id) if isinstance(raw_user_id, str) else None
    except ValueError:
        user_id = None
    user = await session.scalar(select(User).where(User.id == user_id)) if user_id else None
    if user is None or user.github_user_id is None:
        request.session.clear()
        raise APIError(401, "AUTHENTICATION_REQUIRED", "Sign in to continue.")
    return cast(User, user)


async def require_admin_user(
    request: Request, user: Annotated[User, Depends(get_current_user)]
) -> User:
    # Authentication establishes the GitHub identity; this allowlist grants administration.
    if user.github_login.casefold() not in request.app.state.settings.allowed_admin_logins:
        raise APIError(
            403,
            "ADMIN_ACCESS_REQUIRED",
            "This GitHub account is not authorized to manage this Worklog.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin_user)]
MutationOrigin = Annotated[None, Depends(require_same_origin)]

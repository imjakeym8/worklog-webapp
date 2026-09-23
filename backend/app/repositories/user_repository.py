from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import GitHubIdentity


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_github_user(self, identity: GitHubIdentity) -> User:
        # GitHub usernames can change, so identity is matched using GitHub's numeric user ID.
        user = await self.session.scalar(
            select(User).where(User.github_user_id == identity.id).with_for_update()
        )
        now = datetime.now(UTC)
        values = {
            "github_login": identity.login,
            "display_name": identity.name,
            "avatar_url": str(identity.avatar_url) if identity.avatar_url else None,
            "email": identity.email,
            "updated_at": now,
            "last_login_at": now,
        }
        if user is None:
            user = User(github_user_id=identity.id, **values)
            self.session.add(user)
        else:
            for name, value in values.items():
                setattr(user, name, value)
        await self.session.flush()
        return user

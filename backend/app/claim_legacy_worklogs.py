"""Claim preserved pre-authentication worklogs in local development."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.database import create_engine
from app.models.user import User
from app.models.worklog import Worklog

LEGACY_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def claim(github_login: str) -> None:
    settings = Settings()
    if settings.environment != "development":
        raise SystemExit("Legacy worklog claiming is allowed only in development.")
    engine = create_engine(settings)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            async with session.begin():
                user = await session.scalar(
                    select(User).where(
                        User.github_login == github_login, User.github_user_id.is_not(None)
                    )
                )
                if user is None:
                    raise SystemExit("Sign in first, then pass your exact GitHub login.")
                legacy_count = await session.scalar(
                    select(func.count())
                    .select_from(Worklog)
                    .where(Worklog.user_id == LEGACY_USER_ID)
                )
                await session.execute(
                    update(Worklog).where(Worklog.user_id == LEGACY_USER_ID).values(user_id=user.id)
                )
                await session.execute(
                    delete(User).where(
                        User.id == LEGACY_USER_ID,
                        ~User.worklogs.any(),
                    )
                )
        print(f"Claimed {legacy_count or 0} legacy worklog(s) for @{github_login}.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-login", required=True)
    arguments = parser.parse_args()
    asyncio.run(claim(arguments.github_login))

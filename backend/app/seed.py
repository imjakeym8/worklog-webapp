"""Optional, repeatable development seed: python -m app.seed."""

import argparse
import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.core.database import create_engine
from app.models.user import User
from app.models.worklog import Worklog
from app.repositories.worklog_repository import WorklogRepository
from app.schemas.worklog import WorklogCreate


async def seed(github_login: str) -> None:
    settings = Settings()
    if settings.environment != "development":
        raise SystemExit("Seed is allowed only with ENVIRONMENT=development.")
    engine = create_engine(settings)
    samples = [
        WorklogCreate(
            date=date(2026, 9, 10),
            hours=Decimal("6"),
            tracks=["FastAPI Setup", "Backend Development"],
            activity_breakdown="## API foundation\n\nBuilt asynchronous handlers and validation.",
            detailed_notes="Kept database queries separate from HTTP handlers.",
            quick_summary="A working REST API foundation.",
            blockers=["Configuration", "Logging"],
            next=["Database migration"],
        ),
        WorklogCreate(
            date=date(2026, 9, 11),
            hours=Decimal("2.5"),
            shipped=True,
            tracks=["PostgreSQL", "Backend Development"],
            activity_breakdown="Created tables, indexes, and migration tests.",
            quick_summary="Verified persistence across requests.",
            next=["Review validation"],
        ),
        WorklogCreate(
            date=date(2026, 9, 12),
            hours=Decimal("1.25"),
            tracks=["Authentication"],
            activity_breakdown="Reviewed security boundaries and wrote planning notes.",
            detailed_notes="Development service remains local-only.",
        ),
    ]
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
                repository = WorklogRepository(session)
                for sample in samples:
                    exists = await session.scalar(
                        select(Worklog.id).where(
                            Worklog.date == sample.date,
                            Worklog.activity_breakdown == sample.activity_breakdown,
                            Worklog.user_id == user.id,
                        )
                    )
                    if exists is None:
                        await repository.create(sample, user.id)
        print("Development seed complete.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed sample worklogs for a signed-in user.")
    parser.add_argument("--github-login", required=True)
    arguments = parser.parse_args()
    asyncio.run(seed(arguments.github_login))

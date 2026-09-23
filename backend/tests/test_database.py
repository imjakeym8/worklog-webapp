import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command


@pytest.mark.integration
async def test_migration_constraints_and_timestamp_trigger() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    schema = "worklog_test_" + uuid4().hex
    engine = create_async_engine(url, poolclass=NullPool)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))

            def migration_cycle(sync_connection: Connection) -> None:
                config.attributes["connection"] = sync_connection
                command.upgrade(config, "head")
                command.check(config)
                command.downgrade(config, "base")
                command.upgrade(config, "head")

            await connection.run_sync(migration_cycle)
            entry_id, track_id, user_id = uuid4(), uuid4(), uuid4()
            await connection.execute(
                text(
                    "INSERT INTO users (id, github_user_id, github_login) "
                    "VALUES (:id, 9001, 'migration-test')"
                ),
                {"id": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO worklogs (id, user_id, date, hours, activity_breakdown) "
                    "VALUES (:id, :user_id, '2026-09-10', 2.5, 'Activity')"
                ),
                {"id": entry_id, "user_id": user_id},
            )
            created = await connection.scalar(text("SELECT updated_at FROM worklogs"))
            await connection.execute(text("UPDATE worklogs SET shipped = true"))
            updated = await connection.scalar(text("SELECT updated_at FROM worklogs"))
            assert updated > created
            for statement in [
                "UPDATE worklogs SET hours = 0",
                "UPDATE worklogs SET hours = -1",
                "UPDATE worklogs SET activity_breakdown = ' '",
                "UPDATE worklogs SET date = NULL",
            ]:
                with pytest.raises(IntegrityError):
                    async with connection.begin_nested():
                        await connection.execute(text(statement))
            await connection.execute(
                text("INSERT INTO tracks (id, name) VALUES (:id, 'Shared')"), {"id": track_id}
            )
            join = text("INSERT INTO worklog_tracks VALUES (:worklog_id, :track_id)")
            values = {"worklog_id": entry_id, "track_id": track_id}
            await connection.execute(join, values)
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(join, values)
            await connection.execute(text("DELETE FROM worklogs"))
            assert await connection.scalar(text("SELECT count(*) FROM worklog_tracks")) == 0
            assert await connection.scalar(text("SELECT count(*) FROM tracks")) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()

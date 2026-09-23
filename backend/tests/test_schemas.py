from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import APIError
from app.repositories.worklog_repository import Cursor
from app.schemas.worklog import WorklogCreate

SETTINGS_VALUES = {
    "github_client_id": "test-client-id",
    "github_client_secret": "github-secret-that-is-at-least-32-characters",
    "session_secret": "session-secret-that-is-at-least-32-characters",
}


def test_calendar_and_markdown() -> None:
    entry = WorklogCreate(date="2024-02-29", hours=7.25, activity_breakdown="  # Markdown\n")
    assert entry.date == date(2024, 2, 29)
    assert entry.activity_breakdown == "  # Markdown\n"
    with pytest.raises(ValidationError):
        WorklogCreate(date="2025-02-29", hours=1, activity_breakdown="Notes")


def test_cursor_roundtrip_and_invalid_input() -> None:
    cursor = Cursor(date=date(2026, 9, 10), created_at=datetime.now(UTC), id=uuid4())
    assert Cursor.decode(cursor.encode()) == cursor
    for value in ["garbage", "e30", "💥"]:
        with pytest.raises(APIError):
            Cursor.decode(value)


def test_settings_validation() -> None:
    settings = Settings(
        database_url="postgresql://user:secret@localhost/worklog",
        _env_file=None,
        **SETTINGS_VALUES,
    )
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")
    assert "user:secret" not in repr(settings)
    for origin in ["*", "https://example.com/path", "https://user:pass@example.com"]:
        with pytest.raises(ValidationError):
            Settings(
                database_url="postgresql://localhost/worklog",
                frontend_url=origin,
                _env_file=None,
                **SETTINGS_VALUES,
            )
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///worklog.db", _env_file=None, **SETTINGS_VALUES)
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://localhost/worklog",
            session_secret="short",
            _env_file=None,
            **{key: value for key, value in SETTINGS_VALUES.items() if key != "session_secret"},
        )

import pytest

from app.core.errors import APIError
from app.services.markdown_portability_service import (
    export_worklog_markdown,
    parse_worklog_markdown,
)

CANONICAL = b"""---
date: 2026-09-19
tracks: [FastAPI, GitHub]
hours: 4
shipped: false
blockers: [Webhook testing]
next: [Repository sync]
---

# \xf0\x9f\x93\x9d Worklog: 2026-09-19

## \xe2\x8f\xb1\xef\xb8\x8f Activity Breakdown

Worked on repository synchronization.

## \xf0\x9f\x9b\xa0\xef\xb8\x8f Detailed Notes

Kept **Markdown** in the notes.

## \xf0\x9f\x92\xa1 Quick Summary

Sync is ready.
"""


def test_parse_canonical_markdown_and_legacy_blocker() -> None:
    parsed = parse_worklog_markdown(CANONICAL.replace(b"blockers:", b"blocker:"))
    assert parsed.payload.date.isoformat() == "2026-09-19"
    assert parsed.payload.blockers == ["Webhook testing"]
    assert parsed.payload.detailed_notes == "Kept **Markdown** in the notes."


def test_parser_tolerates_optional_sections_and_legacy_none_blocker() -> None:
    content = b"""---
date: 2026-09-09
tracks: [Domain Setup, Github Management]
hours: 6
shipped: false
blocker: None
next: []
---

# Worklog: 2026-09-08

## Activity Breakdown

Built the [API](https://example.test) across multiple paragraphs.

Still validating details.

## Detailed Notes

## Quick Summary

"""
    parsed = parse_worklog_markdown(content)
    assert parsed.payload.date.isoformat() == "2026-09-09"
    assert parsed.payload.blockers == []
    assert parsed.payload.detailed_notes == ""
    assert parsed.payload.quick_summary == ""
    assert parsed.payload.activity_breakdown.endswith("Still validating details.")


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"# missing", "MARKDOWN_FRONTMATTER_INVALID"),
        (CANONICAL.replace(b"hours: 4", b"hours: zero"), "MARKDOWN_HOURS_INVALID"),
        (
            CANONICAL.replace(b"## \xe2\x8f\xb1\xef\xb8\x8f Activity Breakdown", b"## Other"),
            "MARKDOWN_SECTION_MISSING",
        ),
        (CANONICAL.replace(b"tracks: [FastAPI, GitHub]\n", b""), "MARKDOWN_TRACKS_MISSING"),
    ],
)
def test_invalid_markdown_is_actionable(content: bytes, code: str) -> None:
    with pytest.raises(APIError) as error:
        parse_worklog_markdown(content)
    assert error.value.code == code


def test_export_round_trips_canonical_format() -> None:
    parsed = parse_worklog_markdown(CANONICAL)
    # The parser's payload has the exact fields needed by the canonical exporter.
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.schemas.worklog import WorklogResponse

    payload = parsed.payload
    markdown = export_worklog_markdown(
        WorklogResponse(
            id=uuid4(),
            attachment=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            **payload.model_dump(),
        )
    )
    assert parse_worklog_markdown(markdown.encode()).payload == payload

import pytest
from conftest import TestContext

pytestmark = pytest.mark.integration

MARKDOWN = b"""---
date: 2026-09-09
tracks: [FastAPI]
hours: 2
shipped: false
blocker: None
next: []
---

# Worklog: a presentation-only date

## Activity Breakdown

Imported through the normal worklog service.

## Detailed Notes

## Quick Summary
"""


async def import_markdown(
    test_context: TestContext, content: bytes = MARKDOWN, update: str = "false"
):
    return await test_context.http.post(
        "/api/imports/markdown",
        files={"upload": ("journal.md", content, "text/markdown")},
        data={"update": update},
    )


async def test_import_uses_request_scoped_transaction(test_context: TestContext) -> None:
    await test_context.login()
    response = await import_markdown(test_context)
    assert response.status_code == 201, response.text
    worklog = response.json()
    assert worklog["date"] == "2026-09-09"
    assert worklog["blockers"] == []
    assert worklog["detailedNotes"] == ""
    assert (await test_context.http.get(f"/api/worklogs/{worklog['id']}")).status_code == 200

    duplicate = await import_markdown(test_context)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "MARKDOWN_ALREADY_IMPORTED"


async def test_changed_file_requires_explicit_update(test_context: TestContext) -> None:
    await test_context.login()
    first = await import_markdown(test_context)
    assert first.status_code == 201
    changed = MARKDOWN.replace(b"hours: 2", b"hours: 3")
    conflict = await import_markdown(test_context, changed)
    assert conflict.status_code == 409
    updated = await import_markdown(test_context, changed, update="true")
    assert updated.status_code == 201
    assert updated.json()["hours"] == 3

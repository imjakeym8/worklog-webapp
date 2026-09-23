import pytest
from conftest import TestContext

from app.schemas.auth import GitHubIdentity

pytestmark = pytest.mark.integration


async def test_public_routes_hide_private_entries_and_allow_public_reads(
    test_context: TestContext,
) -> None:
    await test_context.login(GitHubIdentity(id=1, login="imjakeym8"))
    private = await test_context.http.post(
        "/api/worklogs",
        json={"date": "2026-09-12", "hours": 1, "activityBreakdown": "Private work"},
    )
    public = await test_context.http.post(
        "/api/worklogs",
        json={
            "date": "2026-09-13",
            "hours": 1,
            "activityBreakdown": "Public work",
            "visibility": "public",
        },
    )
    assert private.status_code == 201
    assert public.status_code == 201

    test_context.http.cookies.clear()
    listing = await test_context.http.get("/api/public/worklogs")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [public.json()["id"]]
    assert "visibility" not in listing.json()["items"][0]
    assert "createdAt" not in listing.json()["items"][0]
    private_lookup = await test_context.http.get(f"/api/public/worklogs/{private.json()['id']}")
    assert private_lookup.status_code == 404


async def test_admin_allowlist_rejects_authenticated_unrelated_user(
    test_context: TestContext,
) -> None:
    await test_context.login(GitHubIdentity(id=2, login="unrelated-user"))
    response = await test_context.http.post(
        "/api/worklogs",
        json={"date": "2026-09-12", "hours": 1, "activityBreakdown": "Blocked"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_ACCESS_REQUIRED"

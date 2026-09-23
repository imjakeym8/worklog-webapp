import pytest
from conftest import TestContext

from app.schemas.auth import GitHubIdentity

pytestmark = pytest.mark.integration
PAYLOAD = {"date": "2026-09-10", "hours": 2, "activityBreakdown": "Owned entry"}


async def test_worklog_queries_are_scoped_to_authenticated_owner(
    test_context: TestContext,
) -> None:
    first = GitHubIdentity(id=2001, login="owner-one")
    second = GitHubIdentity(id=2002, login="owner-two")

    await test_context.login(first)
    first_entry = await test_context.http.post(
        "/api/worklogs", json=PAYLOAD | {"tracks": ["Only One"]}
    )
    assert first_entry.status_code == 201
    first_path = f"/api/worklogs/{first_entry.json()['id']}"
    assert (await test_context.http.get(first_path)).status_code == 200
    assert (await test_context.http.patch(first_path, json={"hours": 3})).status_code == 200

    test_context.http.cookies.clear()
    await test_context.login(second)
    assert (await test_context.http.get("/api/worklogs")).json()["items"] == []
    assert (await test_context.http.get("/api/tracks")).json() == []
    assert (await test_context.http.get(first_path)).status_code == 404
    assert (await test_context.http.patch(first_path, json={"hours": 4})).status_code == 404
    assert (await test_context.http.delete(first_path)).status_code == 404

    second_entry = await test_context.http.post(
        "/api/worklogs", json=PAYLOAD | {"activityBreakdown": "Second owner"}
    )
    assert second_entry.status_code == 201
    second_path = f"/api/worklogs/{second_entry.json()['id']}"
    assert [
        item["id"] for item in (await test_context.http.get("/api/worklogs")).json()["items"]
    ] == [second_entry.json()["id"]]

    test_context.http.cookies.clear()
    await test_context.login(first)
    assert (await test_context.http.get(second_path)).status_code == 404
    assert (await test_context.http.delete(first_path)).status_code == 204
    assert (await test_context.http.get(first_path)).status_code == 404

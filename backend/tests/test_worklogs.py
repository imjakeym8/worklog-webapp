from datetime import datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration
PAYLOAD = {"date": "2026-09-10", "hours": 2.5, "activityBreakdown": "  ## Built API\n\n**Done**  "}


async def create(client: AsyncClient, **changes: object) -> dict:
    response = await client.post("/api/worklogs", json=PAYLOAD | changes)
    assert response.status_code == 201, response.text
    return response.json()


async def test_crud_and_tracks(client: AsyncClient) -> None:
    entry = await create(client, tracks=[" PostgreSQL ", "PostgreSQL", "Backend"])
    path = "/api/worklogs/" + entry["id"]
    assert entry["tracks"] == ["Backend", "PostgreSQL"]
    assert entry["activityBreakdown"] == PAYLOAD["activityBreakdown"]
    assert entry["hours"] == 2.5 and entry["shipped"] is False
    assert datetime.fromisoformat(entry["createdAt"]).tzinfo is not None
    assert (await client.get(path)).json() == entry
    updated = await client.patch(
        path, json={"shipped": True, "tracks": ["PostgreSQL"], "next": ["Test"]}
    )
    assert updated.status_code == 200
    assert updated.json()["updatedAt"] > entry["updatedAt"]
    assert updated.json()["activityBreakdown"] == entry["activityBreakdown"]
    assert (await client.get(path)).json()["shipped"] is True
    assert (await client.patch(path, json={"tracks": [], "next": []})).json()["tracks"] == []
    await create(client, tracks=["PostgreSQL"])
    assert [track["name"] for track in (await client.get("/api/tracks")).json()] == ["PostgreSQL"]
    assert (await client.delete(path)).status_code == 204
    assert (await client.get(path)).status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"date": ""},
        {"date": "2026-02-30"},
        {"date": "2026-9-10"},
        {"date": "2026-09-10T12:00:00Z"},
        {"hours": 0},
        {"hours": -1},
        {"hours": "NaN"},
        {"hours": 1.234},
        {"tracks": "one,two"},
        {"blockers": "one,two"},
        {"next": [""]},
        {"activityBreakdown": "  "},
        {"shipped": "false"},
        {"unknown": 1},
    ],
)
async def test_invalid_create(client: AsyncClient, change: dict) -> None:
    response = await client.post("/api/worklogs", json=PAYLOAD | change)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_required_and_null_fields(client: AsyncClient) -> None:
    assert (await client.post("/api/worklogs", json={})).status_code == 422
    entry = await create(client)
    path = "/api/worklogs/" + entry["id"]
    for field in [
        "date",
        "hours",
        "tracks",
        "blockers",
        "next",
        "activityBreakdown",
        "shipped",
        "detailedNotes",
        "quickSummary",
    ]:
        assert (await client.patch(path, json={field: None})).status_code == 422
    assert (await client.patch(path, json={})).status_code == 422
    assert (await client.patch(path, json={"detailed_notes": "\n# Keep Markdown\n"})).json()[
        "detailedNotes"
    ] == "\n# Keep Markdown\n"


async def test_filters_search_and_ordering(client: AsyncClient) -> None:
    older = await create(client, date="2025-12-31", tracks=["Old"])
    first = await create(
        client,
        tracks=["PostgreSQL"],
        detailedNotes="UniqueNotes",
        quickSummary="UniqueSummary",
        blockers=["UniqueBlocker"],
        next=["UniqueNext"],
    )
    second = await create(client, date="2026-09-11", activityBreakdown="100%_literal")
    same_date = await create(client, date="2026-09-11")
    all_items = (await client.get("/api/worklogs")).json()["items"]
    assert [item["id"] for item in all_items] == [
        same_date["id"],
        second["id"],
        first["id"],
        older["id"],
    ]
    assert len((await client.get("/api/worklogs", params={"year": 2026})).json()["items"]) == 3
    for term in ["postgresql", "UNIQUENOTES", "uniquesummary", "uniqueblocker", "uniquenext"]:
        results = (await client.get("/api/worklogs", params={"search": term})).json()["items"]
        assert [item["id"] for item in results] == [first["id"]]
    assert len((await client.get("/api/worklogs", params={"search": "%_"})).json()["items"]) == 1
    assert (
        len(
            (
                await client.get(
                    "/api/worklogs", params={"year": 2026, "track": "PostgreSQL", "search": "API"}
                )
            ).json()["items"]
        )
        == 1
    )
    assert (await client.get("/api/worklogs", params={"track": "Missing"})).json()["items"] == []


async def test_pagination_and_query_validation(client: AsyncClient) -> None:
    entries = [await create(client) for _ in range(3)]
    ids = []
    params = {"limit": "1"}
    while True:
        response = (await client.get("/api/worklogs", params=params)).json()
        ids.extend(item["id"] for item in response["items"])
        if response["nextCursor"] is None:
            break
        params["cursor"] = response["nextCursor"]
    assert ids == [entry["id"] for entry in reversed(entries)]
    for query in [{"limit": 0}, {"limit": 101}, {"year": 0}, {"year": 10000}, {"cursor": "broken"}]:
        assert (await client.get("/api/worklogs", params=query)).status_code == 422
    assert (await client.get("/api/worklogs/not-a-uuid")).status_code == 422


async def test_not_found_health_and_cors(client: AsyncClient) -> None:
    path = f"/api/worklogs/{uuid4()}"
    for response in [
        await client.get(path),
        await client.patch(path, json={"hours": 1}),
        await client.delete(path),
    ]:
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "WORKLOG_NOT_FOUND"
    assert (await client.get("/health")).json() == {"status": "ok"}
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    preflight = await client.options("/api/worklogs", headers=headers)
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert preflight.headers["access-control-allow-credentials"] == "true"
    headers["Origin"] = "https://untrusted.example"
    assert (
        "access-control-allow-origin"
        not in (await client.options("/api/worklogs", headers=headers)).headers
    )

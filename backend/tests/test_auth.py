from urllib.parse import parse_qs, urlparse

import pytest
from conftest import DEFAULT_IDENTITY, TestContext
from sqlalchemy import func, select

from app.api.auth import get_github_oauth
from app.models.user import User
from app.schemas.auth import GitHubIdentity

pytestmark = pytest.mark.integration


async def test_unauthenticated_current_user_and_protected_worklogs(
    test_context: TestContext,
) -> None:
    assert (await test_context.http.get("/api/auth/me")).status_code == 401
    assert (await test_context.http.get("/api/worklogs")).status_code == 401
    assert (
        await test_context.http.post(
            "/api/worklogs",
            json={"date": "2026-09-10", "hours": 1, "activityBreakdown": "Private"},
        )
    ).status_code == 401


async def test_login_creates_current_user_and_returning_login_updates_profile(
    test_context: TestContext,
) -> None:
    login_response = await test_context.login()
    assert login_response.headers["location"] == "http://localhost:3000/admin"
    session_cookie = login_response.headers["set-cookie"].lower()
    assert "httponly" in session_cookie
    assert "samesite=lax" in session_cookie
    assert "max-age=28800" in session_cookie
    assert "secure" not in session_cookie
    current = await test_context.http.get("/api/auth/me")
    assert current.status_code == 200
    assert current.json() == {
        "id": current.json()["id"],
        "githubLogin": "first-user",
        "displayName": "First User",
        "avatarUrl": "https://avatars.githubusercontent.com/u/1001",
        "isAdmin": True,
    }
    local_user_id = current.json()["id"]

    test_context.http.cookies.clear()
    await test_context.login(
        GitHubIdentity(id=1001, login="renamed-user", name=None, avatar_url=None, email=None)
    )
    updated = (await test_context.http.get("/api/auth/me")).json()
    assert updated["id"] == local_user_id
    assert updated["githubLogin"] == "renamed-user"
    assert updated["displayName"] is None
    async with test_context.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_logout_clears_session(test_context: TestContext) -> None:
    await test_context.login()
    response = await test_context.http.post("/api/auth/logout")
    assert response.status_code == 204
    assert "worklog_session=null" in response.headers["set-cookie"]
    assert (await test_context.http.get("/api/auth/me")).status_code == 401


async def test_oauth_start_uses_state_pkce_and_rejects_invalid_state(
    test_context: TestContext,
) -> None:
    test_context.app.dependency_overrides.pop(get_github_oauth)
    response = await test_context.http.get("/api/auth/github")
    assert response.status_code in {302, 307}
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["state"] and query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"]
    assert "scope" not in query

    failed = await test_context.http.get(
        "/api/auth/github/callback", params={"code": "fake", "state": "wrong"}
    )
    assert failed.status_code == 303
    assert failed.headers["location"] == "http://localhost:3000/?auth=failed"
    assert (await test_context.http.get("/api/auth/me")).status_code == 401

    restart = await test_context.http.get("/api/auth/github")
    valid_state = parse_qs(urlparse(restart.headers["location"]).query)["state"][0]
    denied = await test_context.http.get(
        "/api/auth/github/callback",
        params={"error": "access_denied", "state": valid_state},
    )
    assert denied.status_code == 303
    assert denied.headers["location"] == "http://localhost:3000/?auth=failed"


async def test_tampered_session_is_rejected(test_context: TestContext) -> None:
    await test_context.login()
    session_cookie = test_context.http.cookies.get("worklog_session")
    assert session_cookie
    test_context.http.cookies.clear()
    replacement = "x" if session_cookie[-1] != "x" else "y"
    test_context.http.cookies.set("worklog_session", session_cookie[:-1] + replacement)
    assert (await test_context.http.get("/api/auth/me")).status_code == 401


async def test_mutation_rejects_untrusted_origin(test_context: TestContext) -> None:
    await test_context.login(DEFAULT_IDENTITY)
    response = await test_context.http.post(
        "/api/worklogs",
        headers={"Origin": "https://evil.example"},
        json={"date": "2026-09-10", "hours": 1, "activityBreakdown": "Blocked"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_ORIGIN"

# Worklog

Worklog is a Next.js developer journal backed by a FastAPI REST API and PostgreSQL. GitHub OAuth identifies each user, a signed HTTP-only application session authenticates browser requests, and PostgreSQL remains the persistent source of truth after refreshes and service restarts.

## Repository map

| Path | Purpose |
| --- | --- |
| `app/`, `components/`, `lib/`, `types/` | Next.js routes, UI, frontend API clients, and types. |
| `public/` | Static assets (currently empty). |
| `backend/app/`, `backend/alembic/`, `backend/tests/` | FastAPI source, database migrations, and tests. |
| `backend/pyproject.toml`, `backend/alembic.ini` | Python dependencies and migration configuration. |
| `package.json`, lockfiles, `next.config.ts`, `tsconfig.json` | Frontend dependencies and build configuration. |
| `.env.local.example`, `backend/.env.example` | Placeholder-only environment templates; copy locally, never add real values here. |
| `.gitignore` | Keeps secrets, dependencies, generated output, and local databases out of Git. |

## Production deployment

The portfolio remains at `https://imjakey.dev`. This repository is intended to serve the public journal at `https://worklog.imjakey.dev/`, the protected editor at `/admin`, and FastAPI on the **same origin** at `/api/*`. The previous `/worklog` and `/worklog/admin` paths redirect to `/` and `/admin`. Local development still uses separate Next.js and FastAPI processes as described below.

Import this repository as **one Vercel project**, with Root Directory at the repository root and Framework Preset set to **Services**. The root `vercel.json` defines a Next.js frontend service and a FastAPI service from `backend/`; `/api/*` goes to FastAPI and other paths go to Next.js. `backend/main.py` exposes the FastAPI `app` without replacing the existing factory. Vercel Services must be available on the selected account; validate this configuration with a preview deployment before attaching the custom domain. `pnpm-lock.yaml` is the only lockfile and `pnpm` is the intended frontend package manager. Build output, dependencies, `.vercel/`, and real environment files remain ignored.

Production frontend requests default to same-origin `/api/*`; do **not** set `NEXT_PUBLIC_API_URL` on Vercel unless intentionally overriding that behavior. Keep `NEXT_PUBLIC_API_URL=http://localhost:8000` in local `.env.local` for two-process development. Do not put secrets in any `NEXT_PUBLIC_*` variable.

Set these backend variables in the Vercel project's environment settings, **not** in Git (use the exact names from `backend/.env.example`):

| Variable | Production setting |
| --- | --- |
| `DATABASE_URL` | Hosted PostgreSQL URL using `postgresql+asyncpg://` and the provider's required TLS options; never localhost. |
| `FRONTEND_URL`, `BACKEND_URL` | Both `https://worklog.imjakey.dev`. |
| `ENVIRONMENT` | `production`. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Production GitHub OAuth App credentials. |
| `GITHUB_CALLBACK_URL` | `https://worklog.imjakey.dev/api/auth/github/callback`. |
| `SESSION_SECRET`, `SESSION_MAX_AGE_SECONDS` | Independent signing secret (at least 32 characters); optional session lifetime. |
| `ADMIN_GITHUB_LOGINS` | `imjakeym8,markschwart34`. |
| `STORAGE_BUCKET`, `STORAGE_ENDPOINT`, `STORAGE_REGION`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY` | Private Supabase S3-compatible bucket configuration for attachments. |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_SLUG` | GitHub App server-side settings for repository connection and publishing. |

Configure the production GitHub **OAuth App** Homepage URL as `https://worklog.imjakey.dev` and Authorization callback URL as `https://worklog.imjakey.dev/api/auth/github/callback`. The repository/publishing GitHub **App** uses installation credentials through the GitHub API; this code does not implement a GitHub App callback, setup endpoint, or webhook receiver, so do not invent URLs for those fields. Its public homepage may point to `https://worklog.imjakey.dev`.

Create a hosted PostgreSQL database and a private storage bucket separately. After setting the production backend variables, run migrations from `backend/` in a controlled environment with network access to that database:

```powershell
cd backend
python -m alembic upgrade head
python -m alembic current
```

Do not run migrations against the local database by mistake; no tables are created on app startup. Before promoting the deployment, check `/api/health`, `/`, `/admin`, OAuth return to `/admin`, admin allowlisting, public/private visibility, Markdown import/export, publishing, and private/public attachment delivery. Browser cookies remain `HttpOnly`, `SameSite=Lax`, and `Secure` in production; `FRONTEND_URL` also restricts mutation origins and credentialed CORS to the Worklog origin.

## Architecture and database

`backend/app/api` handles HTTP, `schemas` validates input and produces camelCase responses, `services` coordinates transactions, and `repositories` contains async SQLAlchemy queries. `core` owns typed settings, OAuth, the application session, CSRF checks, and errors. Requests have independent database sessions; mutations commit before returning success. Failed transactions roll back and connections close. Startup does not create tables.

`users` has a local UUID key and a unique immutable GitHub numeric ID. Mutable GitHub login/profile fields are refreshed at every sign-in. `worklogs.user_id` is a required foreign key. List, read, update, delete, track, and search queries are all scoped in SQL to the authenticated user; knowing another worklog UUID returns the same `404` as a missing row.

`worklogs` uses UUID primary keys, DATE, NUMERIC(8,2) hours, text fields, boolean shipped status, and timezone-aware timestamps. PostgreSQL assigns creation timestamps; a trigger refreshes `updated_at`, including direct SQL updates. Track-only edits touch the parent too.

`tracks` stores unique, case-sensitive names. `worklog_tracks` is a many-to-many join with a composite primary key and cascading foreign keys. Labels are trimmed and deduplicated; returned tracks are alphabetized. Unused tracks remain reusable. A chronology index supports reverse ordering and a track-side join index supports filtering.

Blockers and next steps use PostgreSQL `text[]`: these ordered, entry-owned labels need no shared identity or independent lifecycle. Arrays allow atomic replacement without artificial join tables. Markdown text is preserved exactly, including whitespace.

## Local setup

Requires Node.js with pnpm, Python 3.12+, and PostgreSQL (verified with Python 3.14 and PostgreSQL 18). Install the frontend dependencies from the repository root:

```powershell
pnpm install
Copy-Item .env.local.example .env.local
```

The frontend environment contains only the public API location:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Install the backend on PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

On macOS/Linux use `source .venv/bin/activate` and `cp .env.example .env`. All following commands run from `backend/` with its virtual environment active.

`python -m pip install -e .` installs every runtime dependency, including FastAPI, Authlib, HTTPX, Starlette's `itsdangerous` session requirement, S3-compatible storage support, Pillow image validation, and multipart uploads. Run the same command after pulling backend dependency changes to refresh the environment; developers running tests, Ruff, or Mypy can install the optional toolchain with `python -m pip install -e '.[dev]'`.

Create a local role and databases using your PostgreSQL administrator connection:

```sql
CREATE ROLE worklog LOGIN PASSWORD 'replace-with-a-local-password';
CREATE DATABASE worklog OWNER worklog;
CREATE DATABASE worklog_test OWNER worklog;
```

Set `.env` to your actual details. Percent-encode special characters in URL credentials. Never commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required, e.g. `postgresql+asyncpg://worklog:password@localhost:5432/worklog`. Plain `postgresql://` also accepted. |
| `FRONTEND_URL` | Exact credentialed CORS and CSRF origin; local value is `http://localhost:3000`. |
| `BACKEND_URL` | Public backend origin; local value is `http://localhost:8000`. |
| `ENVIRONMENT` | `development` (default), `test`, or `production`. Production requires HTTPS URLs and sets `Secure` on the cookie. |
| `GITHUB_CLIENT_ID` | OAuth app client ID. Server-side configuration. |
| `GITHUB_CLIENT_SECRET` | OAuth app client secret, at least 32 characters. Never expose through `NEXT_PUBLIC_*`. |
| `GITHUB_CALLBACK_URL` | Exact callback, locally `http://localhost:8000/api/auth/github/callback`. |
| `SESSION_SECRET` | Independent random signing secret, at least 32 characters. |
| `SESSION_MAX_AGE_SECONDS` | Rolling session lifetime, default `28800` (8 hours). |
| `STORAGE_BUCKET` | Private S3-compatible bucket used for image bytes. Required to enable attachments. |
| `STORAGE_ENDPOINT` | Optional S3-compatible endpoint, such as a local MinIO endpoint. Omit for AWS S3. |
| `STORAGE_REGION` | Bucket region, default `us-east-1`. |
| `STORAGE_ACCESS_KEY` | Server-side storage credential. Never expose to the frontend. |
| `STORAGE_SECRET_KEY` | Server-side storage credential. Never expose to the frontend. |

Generate a local session secret without reusing the GitHub client secret:

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
```

Create a GitHub OAuth App under GitHub developer settings with:

```text
Homepage URL:               http://localhost:3000
Authorization callback URL: http://localhost:8000/api/auth/github/callback
```

Copy its client ID and client secret into `backend/.env`. GitHub OAuth Apps require one exact callback URL, so create a separate app/configuration for production. This milestone requests no OAuth scope: the authenticated `/user` endpoint supplies public identity, and email remains null when it is not public. Repository permissions are intentionally deferred.

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:create_app --factory --host localhost --port 8000 --reload
```

In a second terminal, start the frontend from the repository root:

```powershell
pnpm run dev
```

Open `http://localhost:3000` and sign in with GitHub. The UI checks `/api/auth/me` before rendering the journal, then loads, creates, edits, and deletes only that user's worklogs. Filters remain client-side for the compact journal dataset; the API loader follows cursor pages in batches of 100 so records are not limited to the first response page.

Seed is optional and repeatable after that account has signed in:

```powershell
python -m app.seed --github-login your-github-login
```

Matching sample dates/activity for that owner are skipped. Run one seed process at a time; it never runs on startup.

Interactive docs: `http://localhost:8000/docs`. Protected calls still require a valid browser session, and mutations require the configured frontend `Origin`. `/health` checks liveness, not database readiness.

## Private image attachments

Each worklog may have one JPEG or PNG image up to 5 MB. The browser uploads it only after the worklog is saved; the backend verifies the actual image bytes with Pillow, limits dimensions to 12,000 by 12,000 pixels, stores the private object through the S3-compatible storage abstraction, and keeps only metadata plus an opaque key in PostgreSQL. Object URLs are never public: authorized owners view images through an authenticated streaming endpoint.

Create a private bucket first, then provide all of `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, and `STORAGE_SECRET_KEY` in `backend/.env`; set `STORAGE_ENDPOINT` when using MinIO or another compatible provider. For example, a local MinIO setup may use `STORAGE_ENDPOINT=http://localhost:9000` and a bucket created without anonymous download access. Attachment actions intentionally return a service error when storage is not configured rather than writing user files into the project directory.

The attachment endpoints are owner-scoped and require the same trusted frontend origin as other mutations:

| Endpoint | Behavior |
| --- | --- |
| `POST /api/worklogs/{id}/attachment` | Multipart field `upload`; attaches the first image and returns metadata. |
| `GET /api/worklogs/{id}/attachment` | Streams the private image for its owner. |
| `PUT /api/worklogs/{id}/attachment` | Safely replaces the existing image. |
| `DELETE /api/worklogs/{id}/attachment` | Removes the object before deleting its metadata. |

Replacing or deleting a worklog removes storage objects before database metadata. If object deletion fails, the metadata remains so the operation can be retried; replacement keeps cleanup metadata for the same reason. Never configure public bucket read access.

## Authentication and request security

`GET /api/auth/github` starts Authlib's authorization-code flow with a cryptographically random state and S256 PKCE. GitHub redirects only to the configured backend callback. The backend validates state, exchanges the one-time code, fetches `/user`, and matches the local account using the GitHub numeric ID. The temporary GitHub access token is used only for that identity request and is never persisted, logged, returned, placed in a URL, or sent to frontend code.

After callback, FastAPI clears the temporary OAuth session and issues a new signed `worklog_session` cookie containing only the local user UUID. The cookie is `HttpOnly`, limited to the `/api` path, `SameSite=Lax`, expires after the configured rolling lifetime, and is `Secure` in production. Logout clears it. Because the session is signed rather than stored in a server-side session table, logout removes the browser's copy; other stolen copies, if any, expire at their signed maximum age. Rotate `SESSION_SECRET` to invalidate all outstanding sessions.

Cookie authentication is paired with explicit CSRF protection. Every `POST`, `PATCH`, and `DELETE` requires an `Origin` header exactly equal to `FRONTEND_URL`; missing, opaque, and foreign origins are rejected. `SameSite=Lax` provides another browser boundary. Credentialed CORS allows only the same configured frontend origin and is not treated as authorization. Keep frontend and backend on `localhost` in development so browser cookie behavior is consistent.

Authentication endpoints:

| Endpoint | Behavior |
| --- | --- |
| `GET /api/auth/github` | Clears any previous application session and redirects to GitHub. |
| `GET /api/auth/github/callback` | Validates the OAuth response, updates the local user, rotates into an application session, and redirects to the frontend. Safe failure redirects use only `?auth=failed`. |
| `GET /api/auth/me` | Returns `id`, `githubLogin`, `displayName`, and `avatarUrl`; returns `401` when signed out. |
| `POST /api/auth/logout` | Requires the trusted frontend origin, clears the application session, and returns `204`. It does not revoke the GitHub OAuth grant. |

## Migrations and existing development data

Revision `0001` creates the original journal tables and timestamp trigger. Revision `0002` creates users, adds required worklog ownership, and replaces the global chronology index with an owner-first chronology index. Revision `0003` creates the one-to-one attachment metadata table and its ownership-preserving foreign key.

```powershell
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

When `0002` encounters pre-authentication worklogs, it preserves them under a clearly marked, non-authenticating legacy owner. It never assigns them to whichever person happens to sign in first. After the intended owner signs in, transfer them explicitly in development:

```powershell
python -m app.claim_legacy_worklogs --github-login your-github-login
```

The command is refused outside `ENVIRONMENT=development`, requires an existing real GitHub-backed user, transfers only the fixed legacy owner's rows, and removes that placeholder when empty. Back up important local data before any migration or ownership transfer.

For later model changes: `python -m alembic revision --autogenerate -m "describe change"`, review, then upgrade. Trigger changes require manual migration edits. `python -m alembic downgrade base` deletes milestone tables and their data: use only on a disposable database or with a recovery plan.

## API contract

Every `/api/worklogs` and `/api/tracks` endpoint requires the signed application session. Mutation bodies never accept `user_id`; the backend assigns the current owner. Cross-owner UUID requests return `404` to avoid confirming that another user's resource exists.

Input accepts camelCase or snake_case text fields; responses use camelCase. Unknown fields are rejected. Date must be a real `YYYY-MM-DD`. Hours must be positive, at most 999999.99, with at most two decimal places. Shipped is a strict boolean. Activity is required/nonblank; notes and summary default to empty strings. Arrays default to empty, with at most 50 nonblank labels: tracks up to 100 characters, blockers/next up to 200. Activity/summary limits are 100,000 characters; notes 1,000,000.

### Create: `POST /api/worklogs`

Request:

```json
{
  "date": "2026-09-10", "hours": 2.5,
  "tracks": ["FastAPI Setup", "PostgreSQL"], "shipped": false,
  "activityBreakdown": "## API\n\nBuilt **CRUD** handlers.",
  "detailedNotes": "Validated persistence.", "quickSummary": "Foundation ready.",
  "blockers": ["Configuration"], "next": ["Tests"]
}
```

Returns `201` and the complete resource (generated ID/timestamps are illustrative):

```json
{
  "id": "5605974c-3cac-499d-89eb-3731389ea837",
  "date": "2026-09-10", "hours": 2.5,
  "tracks": ["FastAPI Setup", "PostgreSQL"], "shipped": false,
  "activityBreakdown": "## API\n\nBuilt **CRUD** handlers.",
  "detailedNotes": "Validated persistence.", "quickSummary": "Foundation ready.",
  "blockers": ["Configuration"], "next": ["Tests"],
  "createdAt": "2026-09-10T12:00:00Z", "updatedAt": "2026-09-10T12:00:00Z"
}
```

### Read: `GET /api/worklogs/{id}`

No request body. Returns `200` with the complete resource above, or `404` if missing.

### List: `GET /api/worklogs`

Example: `/api/worklogs?year=2026&track=FastAPI%20Setup&search=crud&limit=20`.

Optional filters combine with AND: `year` (1–9999), exact case-sensitive `track`, and case-insensitive `search` (up to 500 characters). Search uses parameterized PostgreSQL substring matching across all three text fields, tracks, blockers, and next steps. `%`/`_` match literal characters. This intentionally simple search scans matching text; consider PostgreSQL search indexes if the dataset grows.

Returns `200`, for example with no matches:

```json
{"items": [], "nextCursor": null}
```

Nonempty `items` contain complete resources shown above. Order is `date DESC, created_at DESC, id DESC` for deterministic ties. `limit` defaults to 20, range 1–100. Pass opaque `nextCursor` as the next request's `cursor`, keeping filters unchanged; stop at null. No count query or unbounded worklog response. Cursors represent positions, not snapshots: concurrent date edits may move entries between pages.

### Update: `PATCH /api/worklogs/{id}`

Request example:

```json
{"hours": 3.25, "shipped": true, "tracks": ["PostgreSQL"], "blockers": []}
```

Returns `200` with the complete updated resource and refreshed `updatedAt`. Omitted fields stay unchanged. Arrays replace the whole array; `[]` clears them. Use `""` to clear optional text. Explicit null, empty patches, or invalid input return `422`; missing resource returns `404`.

### Delete: `DELETE /api/worklogs/{id}`

No request body. Returns `204` with no response body. Missing resource returns `404`. Join rows are removed; reusable tracks remain.

### Tracks: `GET /api/tracks`

No request body. Returns `200` with alphabetized labels:

```json
[{"id": "fae1c453-f1dc-40b3-8880-0bf28f264686", "name": "PostgreSQL"}]
```

### Health: `GET /health`

No request body. Returns `200`:

```json
{"status": "ok"}
```

### Errors

Predictable envelopes without SQL, submitted payloads, connection strings, or traces:

```json
{"error": {"code": "WORKLOG_NOT_FOUND", "message": "The requested worklog does not exist."}}
```

Validation returns `422` with `VALIDATION_ERROR` and field/message details. Malformed cursors use `INVALID_CURSOR`. Database conflicts return `409`, database failures `503`, unexpected errors `500` with generic messages.

## Tests and quality checks

Use a dedicated disposable PostgreSQL database, never production. `TEST_DATABASE_URL` is explicit and never falls back to `DATABASE_URL`. Integration tests create unique schemas, apply the actual migration, exercise independent request transactions, then drop only their generated schemas. The test role needs CREATE permission on the database. Without this variable integration tests skip, which is not full verification.

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://worklog:password@localhost:5432/worklog_test'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
```

Coverage includes mocked GitHub user creation/update, OAuth state and PKCE, unauthenticated `/me`, logout, signed sessions, hostile-origin rejection, two-user list isolation, cross-owner read/update/delete attack tests, owned CRUD, persistence, validation, search, ordering, pagination, health, and credentialed restricted CORS. No test calls the real GitHub service. Application code uses strict type checking.

Frontend checks run from the repository root:

```powershell
pnpm run lint
pnpm exec tsc --noEmit
pnpm run build
```

## Markdown portability

Worklogs can be exported from the timeline as canonical UTF-8 Markdown and imported one `.md`
file at a time. Imports use the same authenticated Worklog service as the composer; PostgreSQL
remains the source of truth after import.

The portable format has YAML frontmatter (`date`, `tracks`, `hours`, `shipped`, `blockers`, and
`next`) followed by the `Activity Breakdown`, `Detailed Notes`, and `Quick Summary` sections.
`Activity Breakdown` is required. Legacy `blocker:` frontmatter is accepted and normalized to
`blockers`.

Files are limited to 1 MB and parsed with safe YAML loading. An unchanged local filename/content
pair is rejected as already imported. If the same source filename changes, the UI requires an
explicit update action before replacing the Worklog, so normal journal edits are never silently
overwritten.

## Public journal and administration

The same FastAPI application and PostgreSQL database serve two frontend routes:

| Route | Audience | Access |
| --- | --- | --- |
| `/` | Visitors | Anonymous, read-only public entries only |
| `/admin` | Journal owners | GitHub session plus allowlisted administrator |

GitHub OAuth confirms identity; it does not grant administrative access. Set the backend-only
comma-separated `ADMIN_GITHUB_LOGINS` value to permitted GitHub logins. The local example uses
`imjakeym8,markschwart34`; logins are normalized case-insensitively. Do not put this setting in a
frontend environment variable.

Each Worklog has `private` or `public` visibility. New entries are private, and migration `0006`
marks all existing entries private. Use the admin Visibility selector to deliberately make an entry
public. Website visibility is independent from GitHub Markdown publishing.

Public reads use a separate, read-only API surface:

| Endpoint | Behavior |
| --- | --- |
| `GET /api/public/worklogs` | Lists only public Worklogs. |
| `GET /api/public/worklogs/{id}` | Returns a public Worklog, or `404` for private/missing IDs. |
| `GET /api/public/worklogs/{id}/attachment` | Streams an attachment only after visibility is verified. |
| `GET /api/public/profile` | Returns only the public GitHub identity associated with public entries. |

Public responses omit ownership, visibility administration, import/publishing provenance,
timestamps, storage keys, and attachment IDs. The storage bucket remains private; public attachment
delivery verifies the Worklog is public before retrieving object bytes. Normal Worklog, attachment
mutation, Markdown, and GitHub configuration endpoints require an authenticated allowlisted admin,
then retain existing owner-scoped resource checks and mutation-Origin validation.

### Local access checks

1. Run `python -m alembic upgrade head` in `backend/`.
2. Visit `/` signed out: only public entries and no authoring controls should appear.
3. Visit `/admin` signed out, then authenticate with GitHub.
4. Verify `imjakeym8` and `markschwart34` (or configured local equivalents) can manage their
   owner-scoped journal entries.
5. Verify an unrelated GitHub account sees access denied and receives `403` from protected APIs.
6. Create one private and one public entry; `/` must show only the public entry and only its
   attachment.

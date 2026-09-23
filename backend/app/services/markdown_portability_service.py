from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import cast

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models.markdown_import import MarkdownImport
from app.schemas.worklog import WorklogCreate, WorklogResponse, WorklogUpdate
from app.services.worklog_service import WorklogService

MAX_MARKDOWN_BYTES = 1_000_000
logger = logging.getLogger(__name__)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---(?:\n|\Z)", re.DOTALL)
_HEADING = re.compile(r"^##\s+(?:[^\w]*)(.+?)\s*$", re.MULTILINE)
_SECTION_FIELDS = {
    "activity breakdown": "activity_breakdown",
    "detailed notes": "detailed_notes",
    "quick summary": "quick_summary",
}


@dataclass(frozen=True)
class ParsedMarkdownWorklog:
    payload: WorklogCreate
    content_hash: str


def _import_error(code: str, message: str) -> APIError:
    return APIError(422, code, message)


def _as_string_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if value.strip().casefold() in {"", "none", "null"}:
            return []
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise _import_error(
        "MARKDOWN_FRONTMATTER_INVALID", f"'{field}' must be a string or list of strings."
    )


def parse_worklog_markdown(content: bytes) -> ParsedMarkdownWorklog:
    if len(content) > MAX_MARKDOWN_BYTES:
        raise _import_error("MARKDOWN_FILE_TOO_LARGE", "Markdown files must be 1 MB or smaller.")
    try:
        text = content.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as error:
        raise _import_error(
            "MARKDOWN_FILE_INVALID", "Markdown files must be UTF-8 encoded."
        ) from error
    match = _FRONTMATTER.match(text)
    if not match:
        raise _import_error("MARKDOWN_FRONTMATTER_INVALID", "Markdown frontmatter is required.")
    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        raise _import_error(
            "MARKDOWN_FRONTMATTER_INVALID", "Markdown frontmatter contains invalid YAML."
        ) from error
    if not isinstance(frontmatter, dict):
        raise _import_error(
            "MARKDOWN_FRONTMATTER_INVALID", "Markdown frontmatter must be a mapping."
        )

    sections: dict[str, str] = {}
    headings = list(_HEADING.finditer(text, match.end()))
    for index, heading in enumerate(headings):
        name = heading.group(1).strip().casefold()
        field = _SECTION_FIELDS.get(name)
        if field is not None:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            sections[field] = text[heading.end() : end].strip()
    # Canonical fields may live in frontmatter, but the section body is the portable source.
    activity = sections.get("activity_breakdown", frontmatter.get("activity_breakdown"))
    if not isinstance(activity, str) or not activity.strip():
        raise _import_error(
            "MARKDOWN_SECTION_MISSING", "An Activity Breakdown section is required."
        )
    tracks = frontmatter.get("tracks")
    if tracks is None:
        raise _import_error("MARKDOWN_TRACKS_MISSING", "Markdown frontmatter must include tracks.")
    blockers = frontmatter.get("blockers", frontmatter.get("blocker", []))
    try:
        track_names = _as_string_list(tracks, "tracks")
        if not track_names:
            raise _import_error(
                "MARKDOWN_TRACKS_MISSING", "Markdown frontmatter must include tracks."
            )
        payload = WorklogCreate.model_validate(
            {
                "date": frontmatter.get("date"),
                "tracks": track_names,
                "hours": frontmatter.get("hours"),
                "shipped": frontmatter.get("shipped", False),
                "blockers": _as_string_list(blockers, "blockers"),
                "next": _as_string_list(frontmatter.get("next", []), "next"),
                "activity_breakdown": activity,
                "detailed_notes": sections.get(
                    "detailed_notes", frontmatter.get("detailed_notes", "")
                ),
                "quick_summary": sections.get(
                    "quick_summary", frontmatter.get("quick_summary", "")
                ),
            }
        )
    except ValidationError as error:
        missing_date = any(item["loc"] == ("date",) for item in error.errors())
        code = "MARKDOWN_DATE_MISSING" if missing_date else "MARKDOWN_HOURS_INVALID"
        raise _import_error(code, "Markdown date or hours is invalid.") from error
    return ParsedMarkdownWorklog(payload, hashlib.sha256(content).hexdigest())


def export_worklog_markdown(worklog: WorklogResponse) -> str:
    def yaml_list(values: list[str]) -> str:
        return cast(str, yaml.safe_dump(values, default_flow_style=True)).strip()

    return "\n".join(
        [
            "---",
            f"date: {worklog.date.isoformat()}",
            f"tracks: {yaml_list(worklog.tracks)}",
            f"hours: {worklog.hours}",
            f"shipped: {'true' if worklog.shipped else 'false'}",
            f"blockers: {yaml_list(worklog.blockers)}",
            f"next: {yaml_list(worklog.next)}",
            "---",
            "",
            f"# 📝 Worklog: {worklog.date.isoformat()}",
            "",
            "## ⏱️ Activity Breakdown",
            "",
            worklog.activity_breakdown,
            "",
            "## 🛠️ Detailed Notes",
            "",
            worklog.detailed_notes,
            "",
            "## 💡 Quick Summary",
            "",
            worklog.quick_summary,
            "",
        ]
    )


class MarkdownPortabilityService:
    def __init__(self, session: AsyncSession, worklogs: WorklogService) -> None:
        self.session = session
        self.worklogs = worklogs

    async def import_content(
        self, content: bytes, source_key: str, *, update: bool
    ) -> WorklogResponse:
        try:
            return await self._import_content(content, source_key, update=update)
        except SQLAlchemyError as error:
            # Keep SQL details in development logs; the browser receives only a safe diagnosis.
            logger.exception("Markdown import database operation failed (%s)", type(error).__name__)
            raise APIError(
                503,
                "MARKDOWN_IMPORT_DATABASE_ERROR",
                "Could not import worklog because the database operation failed.",
            ) from error

    async def _import_content(
        self, content: bytes, source_key: str, *, update: bool
    ) -> WorklogResponse:
        parsed = parse_worklog_markdown(content)
        existing = await self.session.scalar(
            select(MarkdownImport).where(
                MarkdownImport.user_id == self.worklogs.user_id,
                or_(
                    MarkdownImport.source_key == source_key,
                    MarkdownImport.content_hash == parsed.content_hash,
                ),
            )
        )
        if existing is not None:
            if existing.content_hash == parsed.content_hash:
                raise APIError(
                    409, "MARKDOWN_ALREADY_IMPORTED", "This Markdown file was already imported."
                )
            if not update:
                raise APIError(
                    409,
                    "MARKDOWN_IMPORT_CONFLICT",
                    "This Markdown file changed; confirm before updating the existing worklog.",
                )
            response = await self.worklogs.update(
                existing.worklog_id, WorklogUpdate(**parsed.payload.model_dump()), commit=False
            )
            existing.content_hash = parsed.content_hash
            return response
        # Reuse the CRUD service and its request-scoped session; commit occurs at dependency exit.
        response = await self.worklogs.create(parsed.payload, commit=False)
        self.session.add(
            MarkdownImport(
                user_id=self.worklogs.user_id,
                worklog_id=response.id,
                source_key=source_key,
                content_hash=parsed.content_hash,
            )
        )
        await self.session.flush()
        return response

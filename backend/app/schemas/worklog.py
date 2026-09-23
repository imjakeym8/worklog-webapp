import re
from datetime import date as CalendarDate
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.schemas.attachment import AttachmentResponse

TrackName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
TrackNames = Annotated[list[TrackName], Field(max_length=50, strict=True)]
Labels = Annotated[list[Label], Field(max_length=50, strict=True)]
Hours = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2, allow_inf_nan=False)]
Activity = Annotated[str, Field(min_length=1, max_length=100_000)]
Notes = Annotated[str, Field(max_length=1_000_000)]
Summary = Annotated[str, Field(max_length=100_000)]
Visibility = Literal["public", "private"]


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class WorklogInput(APIModel):
    @field_validator("date", mode="before", check_fields=False)
    @classmethod
    def validate_iso_date(cls, value: object) -> object:
        if type(value) is CalendarDate:
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Date must be an ISO calendar date (YYYY-MM-DD)")
        return value

    @field_validator("activity_breakdown", check_fields=False)
    @classmethod
    def validate_activity(cls, value: str) -> str:
        if value is None or not value.strip():
            raise ValueError("Activity breakdown must contain text")
        return value

    @field_validator("tracks", "blockers", "next", check_fields=False)
    @classmethod
    def deduplicate_labels(cls, value: list[str]) -> list[str]:
        if value is None:
            raise ValueError("Labels cannot be null; use an empty array to clear them")
        return list(dict.fromkeys(value))


class WorklogCreate(WorklogInput):
    date: CalendarDate
    hours: Hours
    activity_breakdown: Activity
    tracks: TrackNames = Field(default_factory=list)
    shipped: StrictBool = False
    visibility: Visibility = "private"
    blockers: Labels = Field(default_factory=list)
    next: Labels = Field(default_factory=list)
    detailed_notes: Notes = ""
    quick_summary: Summary = ""


class WorklogUpdate(WorklogInput):
    date: CalendarDate | None = None
    hours: Hours | None = None
    activity_breakdown: Activity | None = None
    tracks: TrackNames | None = None
    shipped: StrictBool | None = None
    visibility: Visibility | None = None
    blockers: Labels | None = None
    next: Labels | None = None
    detailed_notes: Notes | None = None
    quick_summary: Summary | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one field to update")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Fields cannot be null; use an empty array or string to clear a field")
        return self


class WorklogResponse(APIModel):
    id: UUID
    date: CalendarDate
    hours: Decimal
    shipped: bool
    visibility: Visibility
    tracks: list[str]
    blockers: list[str]
    next: list[str]
    activity_breakdown: str
    detailed_notes: str
    quick_summary: str
    attachment: AttachmentResponse | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("hours")
    def serialize_hours(self, value: Decimal) -> float:
        return float(value)


class WorklogListResponse(APIModel):
    items: list[WorklogResponse]
    next_cursor: str | None


class PublicAttachmentResponse(APIModel):
    original_filename: str


class PublicWorklogResponse(APIModel):
    id: UUID
    date: CalendarDate
    hours: Decimal
    shipped: bool
    tracks: list[str]
    blockers: list[str]
    next: list[str]
    activity_breakdown: str
    detailed_notes: str
    quick_summary: str
    attachment: PublicAttachmentResponse | None

    @field_serializer("hours")
    def serialize_hours(self, value: Decimal) -> float:
        return float(value)


class PublicWorklogListResponse(APIModel):
    items: list[PublicWorklogResponse]
    next_cursor: str | None


class TrackResponse(APIModel):
    id: UUID
    name: str

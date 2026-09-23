from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: UUID
    worklog_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    created_at: datetime

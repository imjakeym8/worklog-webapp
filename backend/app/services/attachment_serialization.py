from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentResponse


def serialize_attachment(attachment: Attachment) -> AttachmentResponse:
    return AttachmentResponse(
        id=attachment.id,
        worklog_id=attachment.worklog_id,
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        width=attachment.width,
        height=attachment.height,
        created_at=attachment.created_at,
    )

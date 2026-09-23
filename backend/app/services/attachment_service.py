from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.storage import ImageStorage, StorageOperationError
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentResponse
from app.services.attachment_serialization import serialize_attachment
from app.services.worklog_service import WorklogService

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 12_000
ALLOWED_IMAGE_TYPES = {"image/jpeg": "JPEG", "image/png": "PNG"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
# Pillow warns before decoding images above this threshold; the explicit
# dimension check remains final.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_DIMENSION**2


@dataclass(frozen=True)
class ValidatedImage:
    content: bytes
    original_filename: str
    content_type: str
    extension: str
    width: int
    height: int


def safe_display_filename(filename: str | None, extension: str) -> str:
    name = PurePath((filename or "").replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    if not name:
        name = f"image{extension}"
    return name[:255]


async def validate_uploaded_image(upload: UploadFile) -> ValidatedImage:
    filename = upload.filename or ""
    extension = PurePath(filename.replace("\\", "/")).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise APIError(
            422, "ATTACHMENT_TYPE_NOT_ALLOWED", "Only PNG and JPEG images are supported."
        )
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise APIError(
            422, "ATTACHMENT_TYPE_NOT_ALLOWED", "Only PNG and JPEG images are supported."
        )

    content = await upload.read(MAX_IMAGE_SIZE_BYTES + 1)
    if len(content) > MAX_IMAGE_SIZE_BYTES:
        raise APIError(422, "ATTACHMENT_TOO_LARGE", "Image must be 5 MB or smaller.")
    if not content:
        raise APIError(422, "INVALID_IMAGE", "The uploaded file is not a valid image.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as decoded:
                decoded.verify()
            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
                image_format = decoded.format
                width, height = decoded.size
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
    ):
        raise APIError(422, "INVALID_IMAGE", "The uploaded file is not a valid image.") from None

    if image_format not in {"JPEG", "PNG"}:
        raise APIError(
            422, "ATTACHMENT_TYPE_NOT_ALLOWED", "Only PNG and JPEG images are supported."
        )
    content_type = "image/jpeg" if image_format == "JPEG" else "image/png"
    if ALLOWED_IMAGE_TYPES[upload.content_type] != image_format:
        raise APIError(
            422, "ATTACHMENT_TYPE_NOT_ALLOWED", "File type does not match image content."
        )
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise APIError(
            422, "INVALID_IMAGE", "Image dimensions must not exceed 12000 × 12000 pixels."
        )
    expected_extensions = {".jpg", ".jpeg"} if image_format == "JPEG" else {".png"}
    if extension not in expected_extensions:
        raise APIError(
            422, "ATTACHMENT_TYPE_NOT_ALLOWED", "File extension does not match image content."
        )
    return ValidatedImage(
        content=content,
        original_filename=safe_display_filename(filename, extension),
        content_type=content_type,
        extension=".jpg" if image_format == "JPEG" else ".png",
        width=width,
        height=height,
    )


def build_storage_key(user_id: UUID, worklog_id: UUID, extension: str) -> str:
    return f"users/{user_id}/worklogs/{worklog_id}/{uuid4()}{extension}"


class AttachmentService:
    def __init__(
        self, session: AsyncSession, worklogs: WorklogService, storage: ImageStorage
    ) -> None:
        self.session = session
        self.worklogs = worklogs
        self.storage = storage

    async def create(self, worklog_id: UUID, upload: UploadFile) -> AttachmentResponse:
        worklog = await self.worklogs.require_worklog(worklog_id, lock=True)
        if worklog.attachment is not None:
            raise APIError(
                409, "ATTACHMENT_ALREADY_EXISTS", "This worklog already has an image attached."
            )
        image = await validate_uploaded_image(upload)
        storage_key = build_storage_key(self.worklogs.user_id, worklog.id, image.extension)
        try:
            await self.storage.save_image(storage_key, image.content, image.content_type)
        except StorageOperationError as error:
            raise APIError(
                503, "ATTACHMENT_UPLOAD_FAILED", "The image could not be attached."
            ) from error

        attachment = Attachment(
            worklog_id=worklog.id,
            original_filename=image.original_filename,
            storage_key=storage_key,
            content_type=image.content_type,
            size_bytes=len(image.content),
            width=image.width,
            height=image.height,
        )
        self.session.add(attachment)
        try:
            await self.session.flush()
            response = serialize_attachment(attachment)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            try:
                await self.storage.delete_image(storage_key)
            except StorageOperationError:
                pass
            raise
        return response

    async def replace(self, worklog_id: UUID, upload: UploadFile) -> AttachmentResponse:
        worklog = await self.worklogs.require_worklog(worklog_id, lock=True)
        attachment = worklog.attachment
        if attachment is None:
            raise APIError(404, "ATTACHMENT_NOT_FOUND", "This worklog has no image attachment.")
        if attachment.pending_delete_storage_key:
            try:
                await self.storage.delete_image(attachment.pending_delete_storage_key)
            except StorageOperationError as error:
                raise APIError(
                    503,
                    "ATTACHMENT_DELETE_FAILED",
                    "Previous image cleanup must succeed before replacing again.",
                ) from error
            attachment.pending_delete_storage_key = None
        image = await validate_uploaded_image(upload)
        new_storage_key = build_storage_key(self.worklogs.user_id, worklog.id, image.extension)
        try:
            await self.storage.save_image(new_storage_key, image.content, image.content_type)
        except StorageOperationError as error:
            raise APIError(
                503, "ATTACHMENT_UPLOAD_FAILED", "The replacement image could not be attached."
            ) from error

        old_storage_key = attachment.storage_key
        attachment.original_filename = image.original_filename
        attachment.storage_key = new_storage_key
        attachment.content_type = image.content_type
        attachment.size_bytes = len(image.content)
        attachment.width = image.width
        attachment.height = image.height
        attachment.pending_delete_storage_key = old_storage_key
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            try:
                await self.storage.delete_image(new_storage_key)
            except StorageOperationError:
                pass
            raise

        try:
            await self.storage.delete_image(old_storage_key)
        except StorageOperationError:
            raise APIError(
                503,
                "ATTACHMENT_DELETE_FAILED",
                "The new image is attached, but previous image cleanup will be retried.",
            ) from None
        return serialize_attachment(attachment)

    async def get_content(self, worklog_id: UUID) -> tuple[AttachmentResponse, bytes]:
        worklog = await self.worklogs.require_worklog(worklog_id)
        if worklog.attachment is None:
            raise APIError(404, "ATTACHMENT_NOT_FOUND", "This worklog has no image attachment.")
        try:
            content = await self.storage.get_image(worklog.attachment.storage_key)
        except StorageOperationError as error:
            raise APIError(
                503, "ATTACHMENT_RETRIEVAL_FAILED", "The image is unavailable. Try again later."
            ) from error
        return serialize_attachment(worklog.attachment), content

    async def delete(self, worklog_id: UUID) -> None:
        worklog = await self.worklogs.require_worklog(worklog_id, lock=True)
        attachment = worklog.attachment
        if attachment is None:
            raise APIError(404, "ATTACHMENT_NOT_FOUND", "This worklog has no image attachment.")
        await self._delete_stored_images(attachment)
        await self.session.delete(attachment)
        await self.session.commit()

    async def delete_for_worklog(self, worklog_id: UUID) -> None:
        worklog = await self.worklogs.require_worklog(worklog_id, lock=True)
        if worklog.attachment is not None:
            await self._delete_stored_images(worklog.attachment)

    async def _delete_stored_images(self, attachment: Attachment) -> None:
        keys = [attachment.storage_key]
        if attachment.pending_delete_storage_key:
            keys.append(attachment.pending_delete_storage_key)
        try:
            for storage_key in keys:
                await self.storage.delete_image(storage_key)
        except StorageOperationError as error:
            raise APIError(
                503, "ATTACHMENT_DELETE_FAILED", "The image could not be removed."
            ) from error

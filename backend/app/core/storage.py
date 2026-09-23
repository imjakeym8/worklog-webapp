from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import anyio
import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from app.core.config import Settings


class StorageOperationError(Exception):
    """A storage provider operation failed without exposing provider details to clients."""


class ImageStorage(Protocol):
    async def save_image(self, storage_key: str, content: bytes, content_type: str) -> None: ...

    async def get_image(self, storage_key: str) -> bytes: ...

    async def delete_image(self, storage_key: str) -> None: ...


@dataclass(frozen=True)
class UnconfiguredImageStorage:
    async def save_image(self, storage_key: str, content: bytes, content_type: str) -> None:
        raise StorageOperationError("Object storage is not configured")

    async def get_image(self, storage_key: str) -> bytes:
        raise StorageOperationError("Object storage is not configured")

    async def delete_image(self, storage_key: str) -> None:
        raise StorageOperationError("Object storage is not configured")


class S3ImageStorage:
    def __init__(self, settings: Settings) -> None:
        if not settings.storage_is_configured:
            raise ValueError("S3ImageStorage requires configured object storage")
        assert settings.storage_bucket is not None
        assert settings.storage_access_key is not None
        assert settings.storage_secret_key is not None
        self.bucket = settings.storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=str(settings.storage_endpoint) if settings.storage_endpoint else None,
            region_name=settings.storage_region,
            aws_access_key_id=settings.storage_access_key.get_secret_value(),
            aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
            # Supabase's S3 gateway accepts bucket names in the request path,
            # rather than AWS's virtual-host bucket form.
            config=Config(s3={"addressing_style": "path"}),
        )

    async def save_image(self, storage_key: str, content: bytes, content_type: str) -> None:
        try:
            await anyio.to_thread.run_sync(
                lambda: self.client.put_object(
                    Bucket=self.bucket,
                    Key=storage_key,
                    Body=content,
                    ContentType=content_type,
                )
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("Could not store image") from error

    async def get_image(self, storage_key: str) -> bytes:
        try:
            response = await anyio.to_thread.run_sync(
                lambda: self.client.get_object(Bucket=self.bucket, Key=storage_key)
            )
            body = response["Body"]
            try:
                return await anyio.to_thread.run_sync(body.read)
            finally:
                await anyio.to_thread.run_sync(body.close)
        except (BotoCoreError, ClientError, KeyError) as error:
            raise StorageOperationError("Could not read image") from error

    async def delete_image(self, storage_key: str) -> None:
        try:
            await anyio.to_thread.run_sync(
                lambda: self.client.delete_object(Bucket=self.bucket, Key=storage_key)
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageOperationError("Could not delete image") from error


def create_image_storage(settings: Settings) -> ImageStorage:
    if not settings.storage_is_configured:
        return UnconfiguredImageStorage()
    return S3ImageStorage(settings)

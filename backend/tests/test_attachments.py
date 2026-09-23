from io import BytesIO

import pytest
from conftest import TestContext
from PIL import Image

from app.schemas.auth import GitHubIdentity
from app.services.attachment_service import MAX_IMAGE_SIZE_BYTES

pytestmark = pytest.mark.integration
PAYLOAD = {"date": "2026-09-18", "hours": 2, "activityBreakdown": "Attachment test"}


def image_bytes(image_format: str, size: tuple[int, int] = (3, 2)) -> bytes:
    image = Image.new("RGB", size, color=(35, 106, 80))
    output = BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


async def create_worklog(test_context: TestContext) -> dict[str, object]:
    response = await test_context.http.post("/api/worklogs", json=PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()


async def upload(
    test_context: TestContext,
    worklog_id: str,
    *,
    filename: str = "photo.png",
    content: bytes | None = None,
    content_type: str = "image/png",
    method: str = "POST",
):
    return await test_context.http.request(
        method,
        f"/api/worklogs/{worklog_id}/attachment",
        files={"upload": (filename, content or image_bytes("PNG"), content_type)},
    )


async def test_upload_png_jpeg_metadata_and_private_retrieval(test_context: TestContext) -> None:
    await test_context.login()
    png_worklog = await create_worklog(test_context)
    png = image_bytes("PNG")
    upload_response = await upload(test_context, str(png_worklog["id"]), content=png)
    assert upload_response.status_code == 201, upload_response.text
    attachment = upload_response.json()
    assert attachment["originalFilename"] == "photo.png"
    assert attachment["contentType"] == "image/png"
    assert attachment["sizeBytes"] == len(png)
    assert attachment["width"] == 3 and attachment["height"] == 2
    assert len(test_context.storage.saved_keys) == 1
    assert test_context.storage.saved_keys[0].endswith(".png")
    assert "/worklogs/" in test_context.storage.saved_keys[0]

    worklog = await test_context.http.get(f"/api/worklogs/{png_worklog['id']}")
    assert worklog.json()["attachment"]["id"] == attachment["id"]
    preview = await test_context.http.get(f"/api/worklogs/{png_worklog['id']}/attachment")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content == png

    jpeg_worklog = await create_worklog(test_context)
    jpeg_response = await upload(
        test_context,
        str(jpeg_worklog["id"]),
        filename="photo.jpeg",
        content=image_bytes("JPEG"),
        content_type="image/jpeg",
    )
    assert jpeg_response.status_code == 201
    assert jpeg_response.json()["contentType"] == "image/jpeg"


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "code"),
    [
        ("too-large.png", b"x" * (MAX_IMAGE_SIZE_BYTES + 1), "image/png", "ATTACHMENT_TOO_LARGE"),
        ("not-an-image.jpg", b"not an image", "image/jpeg", "INVALID_IMAGE"),
        ("renamed.jpg", image_bytes("PNG"), "image/png", "ATTACHMENT_TYPE_NOT_ALLOWED"),
        ("photo.png", image_bytes("PNG"), "image/jpeg", "ATTACHMENT_TYPE_NOT_ALLOWED"),
        ("photo.gif", image_bytes("PNG"), "image/png", "ATTACHMENT_TYPE_NOT_ALLOWED"),
    ],
    ids=["too-large", "corrupt", "wrong-extension", "wrong-mime", "unsupported-extension"],
)
async def test_upload_rejects_invalid_files(
    test_context: TestContext, filename: str, content: bytes, content_type: str, code: str
) -> None:
    await test_context.login()
    worklog = await create_worklog(test_context)
    response = await upload(
        test_context,
        str(worklog["id"]),
        filename=filename,
        content=content,
        content_type=content_type,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert test_context.storage.objects == {}


async def test_upload_rejects_excessive_dimensions(test_context: TestContext) -> None:
    await test_context.login()
    worklog = await create_worklog(test_context)
    response = await upload(
        test_context,
        str(worklog["id"]),
        content=image_bytes("PNG", (12_001, 1)),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


async def test_single_attachment_replace_remove_and_worklog_delete(
    test_context: TestContext,
) -> None:
    await test_context.login()
    worklog = await create_worklog(test_context)
    path = f"/api/worklogs/{worklog['id']}/attachment"
    first = await upload(test_context, str(worklog["id"]))
    assert first.status_code == 201
    first_key = test_context.storage.saved_keys[-1]
    assert (await upload(test_context, str(worklog["id"]))).status_code == 409

    replacement = await upload(
        test_context,
        str(worklog["id"]),
        filename="replacement.jpg",
        content=image_bytes("JPEG"),
        content_type="image/jpeg",
        method="PUT",
    )
    assert replacement.status_code == 200
    assert first_key in test_context.storage.deleted_keys
    assert replacement.json()["originalFilename"] == "replacement.jpg"

    current_key = test_context.storage.saved_keys[-1]
    assert (await test_context.http.delete(path)).status_code == 204
    assert current_key in test_context.storage.deleted_keys
    assert (await test_context.http.get(path)).status_code == 404

    await upload(test_context, str(worklog["id"]))
    deletion_key = test_context.storage.saved_keys[-1]
    assert (await test_context.http.delete(f"/api/worklogs/{worklog['id']}")).status_code == 204
    assert deletion_key in test_context.storage.deleted_keys


async def test_failed_replacement_preserves_existing_attachment(test_context: TestContext) -> None:
    await test_context.login()
    worklog = await create_worklog(test_context)
    await upload(test_context, str(worklog["id"]))
    original_key = test_context.storage.saved_keys[-1]
    test_context.storage.fail_save = True
    response = await upload(
        test_context,
        str(worklog["id"]),
        filename="new.png",
        method="PUT",
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ATTACHMENT_UPLOAD_FAILED"
    assert original_key in test_context.storage.objects
    current = await test_context.http.get(f"/api/worklogs/{worklog['id']}")
    assert current.json()["attachment"]["originalFilename"] == "photo.png"


async def test_attachment_ownership_and_storage_delete_failure(test_context: TestContext) -> None:
    first = GitHubIdentity(id=3001, login="image-owner")
    second = GitHubIdentity(id=3002, login="image-intruder")
    await test_context.login(first)
    worklog = await create_worklog(test_context)
    await upload(test_context, str(worklog["id"]))
    attachment_path = f"/api/worklogs/{worklog['id']}/attachment"

    test_context.http.cookies.clear()
    assert (await test_context.http.get(attachment_path)).status_code == 401
    await test_context.login(second)
    assert (await upload(test_context, str(worklog["id"]))).status_code == 404
    assert (await test_context.http.get(attachment_path)).status_code == 404
    assert (await test_context.http.delete(attachment_path)).status_code == 404
    assert (await upload(test_context, str(worklog["id"]), method="PUT")).status_code == 404

    test_context.http.cookies.clear()
    await test_context.login(first)
    test_context.storage.fail_delete = True
    failed_delete = await test_context.http.delete(f"/api/worklogs/{worklog['id']}")
    assert failed_delete.status_code == 503
    assert (await test_context.http.get(f"/api/worklogs/{worklog['id']}")).status_code == 200

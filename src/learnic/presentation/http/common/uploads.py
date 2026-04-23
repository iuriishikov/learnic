"""Upload helpers shared between routes that accept ``UploadFile`` bodies."""

from fastapi import UploadFile

from learnic.entities.file.constants import MAX_FILE_SIZE_BYTES
from learnic.entities.file.errors import FileTooLargeError


async def read_image_upload(file: UploadFile) -> tuple[bytes, str]:
    """Read the body and return ``(bytes, content_type)``.

    Aborts early if the body is bigger than the VO limit — avoids
    buffering arbitrary user uploads into memory.

    Args:
        file: Incoming ``multipart/form-data`` field.

    Returns:
        Tuple of raw bytes and the declared ``content_type``. Falls
        back to ``application/octet-stream`` when the client sent none.

    Raises:
        FileTooLargeError: Payload exceeds :data:`MAX_FILE_SIZE_BYTES`.
    """
    data = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(MAX_FILE_SIZE_BYTES)
    content_type = file.content_type or "application/octet-stream"
    return data, content_type

"""Upload helpers shared between routes that accept ``UploadFile`` bodies."""

from fastapi import UploadFile

from learnic.entities.file.errors import FileTooLargeError


async def read_upload(
    file: UploadFile,
    *,
    max_bytes: int,
) -> tuple[bytes, str]:
    """Read the body and return ``(bytes, content_type)``.

    The size cap is **mandatory** and keyword-only: routes must
    import the matching constant from
    :mod:`learnic.presentation.http.common.upload_limits` and pass it
    explicitly. There is no global ``MAX_FILE_SIZE_BYTES`` fallback —
    omitting ``max_bytes`` is a ``TypeError`` at runtime and a mypy
    error at static-analysis time. This forces the choice "how big
    can this particular upload be" to be visible at the call site
    rather than buried in a shared constant.

    The reader pulls at most ``max_bytes + 1`` bytes off the request
    body so an over-cap payload never lands in memory beyond a single
    extra byte.

    Args:
        file: Incoming ``multipart/form-data`` field.
        max_bytes: Per-call-site cap in bytes. See
            ``upload_limits.py`` for the standard constants.

    Returns:
        Tuple of raw bytes and the declared ``content_type``. Falls
        back to ``application/octet-stream`` when the client sent none.

    Raises:
        FileTooLargeError: Payload exceeds ``max_bytes``; the error
            carries ``max_bytes`` as ``limit`` so the SPA can render
            "limit was X MB" without guessing.
    """
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise FileTooLargeError(max_bytes)
    content_type = file.content_type or "application/octet-stream"
    return data, content_type

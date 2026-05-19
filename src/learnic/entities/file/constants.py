from typing import Final

STORAGE_NAME_MAX_LEN: Final = 255
STORAGE_BUCKET_MAX_LEN: Final = 63
CONTENT_TYPE_MAX_LEN: Final = 64

# Per-call-site upload size caps live in
# ``learnic/presentation/http/common/upload_limits.py``. There is no
# longer a single global ``MAX_FILE_SIZE_BYTES`` — every route reading
# an ``UploadFile`` must pass an explicit ``max_bytes`` kwarg to
# :func:`learnic.presentation.http.common.uploads.read_upload` so the
# choice is visible at the call site (avatars stay small, lesson
# videos can be hundreds of MB, etc.).

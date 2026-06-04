from learnic.entities.common.value_object import ValueObject
from learnic.entities.file.constants import (
    CONTENT_TYPE_MAX_LEN,
    STORAGE_BUCKET_MAX_LEN,
    STORAGE_NAME_MAX_LEN,
)
from learnic.entities.file.errors import (
    InvalidContentTypeError,
    InvalidFileSizeError,
    InvalidStorageBucketError,
    InvalidStorageNameError,
)


class StorageName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > STORAGE_NAME_MAX_LEN:
            raise InvalidStorageNameError


class StorageBucket(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > STORAGE_BUCKET_MAX_LEN:
            raise InvalidStorageBucketError


class ContentType(ValueObject):
    """MIME type as reported by the uploader.

    Stored as-is — we only enforce that it's non-empty and fits in the
    column. Accepting any valid MIME keeps the type extensible for any
    kind of file the product needs to store later.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > CONTENT_TYPE_MAX_LEN:
            raise InvalidContentTypeError


class FileSize(ValueObject):
    """Persisted size of an uploaded blob in bytes.

    Only the "positive integer" invariant lives here. Upper bounds are
    enforced **per-call-site** at the HTTP boundary via
    :func:`learnic.presentation.http.common.uploads.open_upload` —
    that's where the policy "an avatar caps at 5 MB but a lesson video
    can be 500 MB" belongs, and a single global ``MAX_FILE_SIZE_BYTES``
    here would hide the choice from the caller.
    """

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidFileSizeError

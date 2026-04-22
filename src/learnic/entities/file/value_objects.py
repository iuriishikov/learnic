from learnic.entities.common.value_object import ValueObject
from learnic.entities.file.constants import (
    CONTENT_TYPE_MAX_LEN,
    MAX_FILE_SIZE_BYTES,
    STORAGE_BUCKET_MAX_LEN,
    STORAGE_NAME_MAX_LEN,
)
from learnic.entities.file.errors import (
    FileTooLargeError,
    InvalidContentTypeError,
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
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0 or self.value > MAX_FILE_SIZE_BYTES:
            raise FileTooLargeError(MAX_FILE_SIZE_BYTES)

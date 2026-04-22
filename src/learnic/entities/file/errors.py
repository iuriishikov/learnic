from learnic.entities.common.errors import FieldError


class InvalidContentTypeError(FieldError):
    """Raised when the content-type string is empty or too long."""


class FileTooLargeError(FieldError):
    """Raised when the uploaded file exceeds the configured size limit."""

    limit: int


class InvalidStorageNameError(FieldError):
    """Raised when the storage-side name is empty or too long."""


class InvalidStorageBucketError(FieldError):
    """Raised when the bucket name is empty or too long."""

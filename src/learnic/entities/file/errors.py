from learnic.entities.common.errors import FieldError


class InvalidContentTypeError(FieldError):
    """Raised when the content-type string is empty or too long."""


class FileTooLargeError(FieldError):
    """Raised when an uploaded file exceeds the per-call-site cap.

    The ``limit`` is the cap chosen by the route reading the upload
    (see ``learnic.presentation.http.common.upload_limits``). There is
    no longer a global cap — this error always carries the
    context-specific value the caller passed to
    ``read_upload(..., max_bytes=...)``.
    """

    limit: int


class InvalidFileSizeError(FieldError):
    """Raised when a persisted file size is not a positive integer.

    A defensive invariant on the :class:`FileSize` VO — applied when
    constructing a ``File`` entity, after the call-site cap has
    already passed at the HTTP boundary. Hitting this in production
    means a corrupted upload or a malformed direct DB insert.
    """


class InvalidStorageNameError(FieldError):
    """Raised when the storage-side name is empty or too long."""


class InvalidStorageBucketError(FieldError):
    """Raised when the bucket name is empty or too long."""

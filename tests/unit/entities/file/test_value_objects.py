import pytest

from learnic.entities.file.constants import CONTENT_TYPE_MAX_LEN
from learnic.entities.file.errors import (
    InvalidContentTypeError,
    InvalidFileSizeError,
    InvalidStorageBucketError,
    InvalidStorageNameError,
)
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)


class TestContentType:
    @pytest.mark.parametrize(
        "value",
        [
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
            "video/mp4",
            "text/plain",
        ],
    )
    def test_accepts_any_non_empty_mime(self, value: str) -> None:
        assert ContentType(value).value == value

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidContentTypeError):
            ContentType("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidContentTypeError):
            ContentType("x" * (CONTENT_TYPE_MAX_LEN + 1))


class TestFileSize:
    def test_accepts_positive(self) -> None:
        assert FileSize(1).value == 1
        assert FileSize(10 * 1024 * 1024 * 1024).value == 10 * 1024 * 1024 * 1024

    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_non_positive(self, value: int) -> None:
        with pytest.raises(InvalidFileSizeError):
            FileSize(value)


class TestStorageName:
    def test_accepts_normal_name(self) -> None:
        assert StorageName("abc.jpg").value == "abc.jpg"

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidStorageNameError):
            StorageName("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidStorageNameError):
            StorageName("x" * 256)


class TestStorageBucket:
    def test_accepts_normal(self) -> None:
        assert StorageBucket("learnic").value == "learnic"

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidStorageBucketError):
            StorageBucket("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidStorageBucketError):
            StorageBucket("x" * 64)

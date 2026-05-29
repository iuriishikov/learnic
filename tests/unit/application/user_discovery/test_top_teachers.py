import uuid
from unittest.mock import AsyncMock

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileMeta
from learnic.application.common.persistence.teacher_ranking import (
    TopTeacherView,
)
from learnic.application.queries.user.top_teachers import (
    GetTopTeachersQuery,
    GetTopTeachersQueryHandler,
)
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID


def _view(
    *,
    student_count: int,
    avatar: FileMeta | None = None,
) -> TopTeacherView:
    return TopTeacherView(
        oid=UserID(uuid.uuid4()),
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        patronymic=None,
        is_verified=True,
        avatar=avatar,
        student_count=student_count,
        published_product_count=3,
    )


async def test_maps_view_fields_and_builds_full_name() -> None:
    view = _view(student_count=42)
    reader = AsyncMock()
    reader.top_by_students = AsyncMock(return_value=[view])
    file_storage = AsyncMock()

    handler = GetTopTeachersQueryHandler(
        reader=reader, file_storage=file_storage,
    )
    result = await handler.run(
        GetTopTeachersQuery(pagination=Pagination(limit=20, offset=0)),
    )

    assert len(result) == 1
    out = result[0]
    assert out.oid == view.oid
    # Canonical Russian-style display order: Last First (no patronymic).
    assert out.full_name == "Lovelace Ada"
    # Email is masked before leaving the application layer.
    assert out.email == "a*****a@example.com"
    assert out.is_verified is True
    assert out.student_count == 42
    assert out.published_product_count == 3
    assert out.avatar is None
    # No avatar => storage is never signed.
    file_storage.presigned_get_url.assert_not_awaited()


async def test_resolves_avatar_to_presigned_url() -> None:
    avatar = FileMeta(
        oid=FileID(uuid.uuid4()),
        storage_name="avatars/ada.jpg",
        bucket="learnic",
        content_type="image/jpeg",
        size_bytes=1024,
    )
    reader = AsyncMock()
    reader.top_by_students = AsyncMock(
        return_value=[_view(student_count=7, avatar=avatar)],
    )
    file_storage = AsyncMock()
    file_storage.presigned_get_url = AsyncMock(
        return_value="https://s3.example.com/signed",
    )

    handler = GetTopTeachersQueryHandler(
        reader=reader, file_storage=file_storage,
    )
    result = await handler.run(
        GetTopTeachersQuery(pagination=Pagination(limit=20, offset=0)),
    )

    out = result[0]
    assert out.avatar is not None
    assert out.avatar.oid == avatar.oid
    assert out.avatar.url == "https://s3.example.com/signed"
    file_storage.presigned_get_url.assert_awaited_once()


async def test_forwards_pagination_to_reader() -> None:
    reader = AsyncMock()
    reader.top_by_students = AsyncMock(return_value=[])
    file_storage = AsyncMock()

    handler = GetTopTeachersQueryHandler(
        reader=reader, file_storage=file_storage,
    )
    pagination = Pagination(limit=5, offset=10)
    result = await handler.run(GetTopTeachersQuery(pagination=pagination))

    assert result == []
    reader.top_by_students.assert_awaited_once_with(pagination=pagination)

import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
)
from learnic.entities.product.errors import ProductDoesNotSupportError
from learnic.application.common.persistence.note_content import (
    NoteDraftView,
    DraftLessonView,
    DraftModuleView,
)
from learnic.application.queries.note_content.get_draft import (
    GetNoteDraftQuery,
    GetNoteDraftQueryHandler,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


def _allow_authorizer() -> AsyncMock:
    authorizer = AsyncMock()
    authorizer.require = AsyncMock(return_value=None)
    return authorizer


def _deny_authorizer() -> AsyncMock:
    authorizer = AsyncMock()
    authorizer.require = AsyncMock(
        side_effect=InsufficientPermissionsError(
            user_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            permission=Permission.READ_PRODUCT.value,
        ),
    )
    return authorizer


async def test_get_draft_returns_view_for_authorized_caller() -> None:
    author_id = UserID(uuid.uuid4())
    note = Product.create_note(
        author_id=author_id,
        name=ProductTitle("Async"),
    )

    expected = NoteDraftView(
        product_id=ProductID(note.oid),
        modules=[
            DraftModuleView(
                oid=NoteModuleID(uuid.uuid4()),
                title="Intro",
                description=None,
                position=0,
                lessons=[
                    DraftLessonView(
                        oid=NoteLessonID(uuid.uuid4()),
                        title="L1",
                        position=0,
                        blocks=[],
                    ),
                ],
            ),
        ],
    )

    product_gateway = AsyncMock()
    product_gateway.with_id = AsyncMock(return_value=note)
    reader = AsyncMock()
    reader.get_draft = AsyncMock(return_value=expected)
    authorizer = _allow_authorizer()

    handler = GetNoteDraftQueryHandler(
        authorizer=authorizer,
        product_gateway=product_gateway,
        content_reader=reader,
    )
    result = await handler.run(
        GetNoteDraftQuery(
            actor_id=author_id,
            product_id=ProductID(note.oid),
        ),
    )
    assert result is expected
    authorizer.require.assert_awaited_once()


async def test_get_draft_without_permission_raises() -> None:
    author_id = UserID(uuid.uuid4())
    other = UserID(uuid.uuid4())
    note = Product.create_note(
        author_id=author_id,
        name=ProductTitle("Async"),
    )
    product_gateway = AsyncMock()
    product_gateway.with_id = AsyncMock(return_value=note)
    reader = AsyncMock()
    handler = GetNoteDraftQueryHandler(
        authorizer=_deny_authorizer(),
        product_gateway=product_gateway,
        content_reader=reader,
    )
    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            GetNoteDraftQuery(
                actor_id=other,
                product_id=ProductID(note.oid),
            ),
        )


async def test_get_draft_missing_raises() -> None:
    author_id = UserID(uuid.uuid4())
    product_gateway = AsyncMock()
    product_gateway.with_id = AsyncMock(return_value=None)
    reader = AsyncMock()
    handler = GetNoteDraftQueryHandler(
        authorizer=_allow_authorizer(),
        product_gateway=product_gateway,
        content_reader=reader,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetNoteDraftQuery(
                actor_id=author_id,
                product_id=ProductID(uuid.uuid4()),
            ),
        )

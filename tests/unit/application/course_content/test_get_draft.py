import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotACourseError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.course_content import (
    CourseDraftView,
    DraftLessonView,
    DraftModuleView,
)
from learnic.application.queries.course_content.get_draft import (
    GetCourseDraftQuery,
    GetCourseDraftQueryHandler,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID


async def test_get_draft_returns_view_for_author() -> None:
    author_id = UserID(uuid.uuid4())
    course = Product.create_course(
        author_id=author_id,
        name=ProductTitle("Async"),
    )

    expected = CourseDraftView(
        product_id=ProductID(course.oid),
        modules=[
            DraftModuleView(
                oid=CourseModuleID(uuid.uuid4()),
                title="Intro",
                description=None,
                position=0,
                lessons=[
                    DraftLessonView(
                        oid=CourseLessonID(uuid.uuid4()),
                        title="L1",
                        position=0,
                        blocks=[],
                    ),
                ],
            ),
        ],
    )

    product_gateway = AsyncMock()
    product_gateway.with_id = AsyncMock(return_value=course)
    reader = AsyncMock()
    reader.get_draft = AsyncMock(return_value=expected)

    handler = GetCourseDraftQueryHandler(
        product_gateway=product_gateway,
        content_reader=reader,
    )
    result = await handler.run(
        GetCourseDraftQuery(
            actor_id=author_id,
            product_id=ProductID(course.oid),
        ),
    )
    assert result is expected


async def test_get_draft_non_owner_raises() -> None:
    author_id = UserID(uuid.uuid4())
    other = UserID(uuid.uuid4())
    course = Product.create_course(
        author_id=author_id,
        name=ProductTitle("Async"),
    )
    product_gateway = AsyncMock()
    product_gateway.with_id = AsyncMock(return_value=course)
    reader = AsyncMock()
    handler = GetCourseDraftQueryHandler(
        product_gateway=product_gateway,
        content_reader=reader,
    )
    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            GetCourseDraftQuery(
                actor_id=other,
                product_id=ProductID(course.oid),
            ),
        )


async def test_get_draft_webinar_raises() -> None:
    author_id = UserID(uuid.uuid4())
    webinar = Product.create_webinar(
        author_id=author_id,
        name=ProductTitle("Live"),
    )
    product_gateway = AsyncMock()
    product_gateway.with_id = AsyncMock(return_value=webinar)
    reader = AsyncMock()
    handler = GetCourseDraftQueryHandler(
        product_gateway=product_gateway,
        content_reader=reader,
    )
    with pytest.raises(NotACourseError):
        await handler.run(
            GetCourseDraftQuery(
                actor_id=author_id,
                product_id=ProductID(webinar.oid),
            ),
        )


async def test_get_draft_missing_raises() -> None:
    author_id = UserID(uuid.uuid4())
    product_gateway = AsyncMock()
    product_gateway.with_id = AsyncMock(return_value=None)
    reader = AsyncMock()
    handler = GetCourseDraftQueryHandler(
        product_gateway=product_gateway,
        content_reader=reader,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetCourseDraftQuery(
                actor_id=author_id,
                product_id=ProductID(uuid.uuid4()),
            ),
        )

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.course_block.models import (
    HtmlBlock,
    KatexBlock,
    RutubeVideoBlock,
)
from learnic.entities.course_block.value_objects import (
    HtmlContent,
    KatexSource,
    RutubeVideoID,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_lesson.value_objects import LessonTitle
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_authorizer() -> AsyncMock:
    az = AsyncMock()
    az.require = AsyncMock()
    az.effective_permissions = AsyncMock(return_value=None)
    return az


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_lesson_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_block_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    gw.list_for_lesson = AsyncMock(return_value=[])
    gw.add_html = AsyncMock()
    gw.update_html = AsyncMock()
    gw.add_katex = AsyncMock()
    gw.update_katex = AsyncMock()
    gw.add_rutube_video = AsyncMock()
    gw.update_rutube_video = AsyncMock()
    gw.delete = AsyncMock()
    gw.reorder = AsyncMock()
    return gw


@pytest.fixture
def fake_html_sanitizer() -> MagicMock:
    sanitizer = MagicMock()
    sanitizer.sanitize = MagicMock(side_effect=lambda raw: raw)
    return sanitizer


@pytest.fixture
def fake_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def other_user_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def course_product(author_id: UserID) -> Product:
    return Product.create_course(
        author_id=author_id,
        name=ProductTitle("Async Python"),
    )


@pytest.fixture
def course_lesson(course_product: Product) -> CourseLesson:
    return CourseLesson.create(
        module_id=CourseModuleID(uuid.uuid4()),
        product_id=ProductID(course_product.oid),
        title=LessonTitle("Lesson 1"),
        position=0,
    )


@pytest.fixture
def html_block(course_lesson: CourseLesson) -> HtmlBlock:
    return HtmlBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        html=HtmlContent("<p>existing</p>"),
        position=0,
    )


@pytest.fixture
def latex_block(course_lesson: CourseLesson) -> KatexBlock:
    return KatexBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        source=KatexSource("E=mc^2"),
        position=1,
    )


_RUTUBE_ID = "f9bb1e0bdfac28c93c2c35a45f87f3eb"


@pytest.fixture
def rutube_video_block(course_lesson: CourseLesson) -> RutubeVideoBlock:
    return RutubeVideoBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        external_id=RutubeVideoID(_RUTUBE_ID),
        position=2,
    )

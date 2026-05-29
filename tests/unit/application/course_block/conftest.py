import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.course_block.ids import CollageItemID
from learnic.entities.course_block.models import (
    ChoiceOption,
    CodeBlock,
    CodeTab,
    CollageItem,
    FileBlock,
    HtmlBlock,
    KatexBlock,
    MultiChoiceBlock,
    PhotoCollageBlock,
    RutubeVideoBlock,
    SingleChoiceBlock,
    TextInputBlock,
    VideoFileBlock,
)
from learnic.entities.course_block.value_objects import (
    AcceptedAnswer,
    ChoiceOptionLabel,
    CodeLanguage,
    CodeSource,
    CodeTabLabel,
    HtmlContent,
    KatexSource,
    RutubeVideoID,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_lesson.value_objects import LessonTitle
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
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
    gw.add_code = AsyncMock()
    gw.update_code = AsyncMock()
    gw.add_single_choice = AsyncMock()
    gw.update_single_choice = AsyncMock()
    gw.add_multi_choice = AsyncMock()
    gw.update_multi_choice = AsyncMock()
    gw.add_text_input = AsyncMock()
    gw.update_text_input = AsyncMock()
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


@pytest.fixture
def code_block(course_lesson: CourseLesson) -> CodeBlock:
    return CodeBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        tabs=[
            CodeTab(
                label=CodeTabLabel(""),
                source=CodeSource("const x = 1;"),
                language=CodeLanguage("ts"),
            ),
        ],
        position=3,
    )


def _options_pair() -> list[ChoiceOption]:
    return [
        ChoiceOption.create(ChoiceOptionLabel("Yes")),
        ChoiceOption.create(ChoiceOptionLabel("No")),
    ]


@pytest.fixture
def single_choice_block(course_lesson: CourseLesson) -> SingleChoiceBlock:
    options = _options_pair()
    return SingleChoiceBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        options=options,
        correct_option_id=options[0].oid,
        position=4,
    )


@pytest.fixture
def multi_choice_block(course_lesson: CourseLesson) -> MultiChoiceBlock:
    options = _options_pair()
    return MultiChoiceBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        options=options,
        correct_option_ids=frozenset({options[0].oid}),
        position=5,
    )


@pytest.fixture
def text_input_block(course_lesson: CourseLesson) -> TextInputBlock:
    return TextInputBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        accepted_answers=[AcceptedAnswer("Paris")],
        case_sensitive=False,
        trim_whitespace=True,
        position=6,
    )


@pytest.fixture
def fake_file_uploads() -> MagicMock:
    """Stub ``FileUploadService`` for file-backed block handlers.

    ``upload`` returns a fresh ``File`` whose ``size_bytes`` mirror
    the uploaded payload, so callers get a real ``oid`` to link and
    the size is consistent with ``len(data)``. The other methods are
    bare awaitables so tests can assert (non-)invocation.
    """

    def _build_file(
        data: bytes,
        content_type: str,
        uploaded_by: UserID,
    ) -> File:
        return File(
            oid=FileID(uuid.uuid4()),
            storage_name=StorageName(str(uuid.uuid4())),
            bucket=StorageBucket("test-bucket"),
            content_type=ContentType(content_type),
            size_bytes=FileSize(len(data)),
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

    svc = MagicMock()
    svc.upload = AsyncMock(side_effect=_build_file)
    svc.soft_delete_previous = AsyncMock()
    svc.previous_file_size = AsyncMock(return_value=0)
    return svc


@pytest.fixture
def fake_entitlement() -> AsyncMock:
    """Stub ``EntitlementService`` — both quota gates are no-ops.

    Tests that exercise the over-quota path set
    ``ensure_can_upload.side_effect`` (or the replace variant) to a
    ``StorageQuotaExceededError`` per case.
    """
    svc = AsyncMock()
    svc.ensure_can_upload = AsyncMock()
    svc.ensure_can_replace_upload = AsyncMock()
    return svc


@pytest.fixture
def file_block(course_lesson: CourseLesson) -> FileBlock:
    return FileBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        file_id=FileID(uuid.uuid4()),
        position=0,
    )


@pytest.fixture
def video_file_block(course_lesson: CourseLesson) -> VideoFileBlock:
    return VideoFileBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        file_id=FileID(uuid.uuid4()),
        position=0,
    )


@pytest.fixture
def photo_collage_block(course_lesson: CourseLesson) -> PhotoCollageBlock:
    return PhotoCollageBlock.create(
        lesson_id=CourseLessonID(course_lesson.oid),
        product_id=course_lesson.product_id,
        items=[
            CollageItem(
                oid=CollageItemID(uuid.uuid4()),
                file_id=FileID(uuid.uuid4()),
            ),
        ],
        position=0,
    )

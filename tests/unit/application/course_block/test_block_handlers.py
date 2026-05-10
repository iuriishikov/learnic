import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.course_block.add_code import (
    AddCodeBlockCommand,
    AddCodeBlockCommandHandler,
    CodeTabInput,
)
from learnic.application.commands.course_block.add_html import (
    AddHtmlBlockCommand,
    AddHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.add_katex import (
    AddKatexBlockCommand,
    AddKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.add_rutube_video import (
    AddRutubeVideoBlockCommand,
    AddRutubeVideoBlockCommandHandler,
)
from learnic.application.commands.course_block.delete import (
    DeleteLessonBlockCommand,
    DeleteLessonBlockCommandHandler,
)
from learnic.application.commands.course_block.reorder import (
    ReorderLessonBlocksCommand,
    ReorderLessonBlocksCommandHandler,
)
from learnic.application.commands.course_block.update_code import (
    UpdateCodeBlockCommand,
    UpdateCodeBlockCommandHandler,
)
from learnic.application.commands.course_block.update_html import (
    UpdateHtmlBlockCommand,
    UpdateHtmlBlockCommandHandler,
)
from learnic.application.commands.course_block.update_katex import (
    UpdateKatexBlockCommand,
    UpdateKatexBlockCommandHandler,
)
from learnic.application.commands.course_block.update_rutube_video import (
    UpdateRutubeVideoBlockCommand,
    UpdateRutubeVideoBlockCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    InvalidReorderError,
    WrongBlockTypeError,
)
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.errors import (
    DuplicateCodeTabLabelError,
    UnsupportedCodeLanguageError,
)
from learnic.entities.course_block.models import (
    CodeBlock,
    HtmlBlock,
    KatexBlock,
    RutubeVideoBlock,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


# ---- add_html ----


async def test_add_html_block_appends_at_next_position(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = [html_block]
    handler = AddHtmlBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        html_sanitizer=fake_html_sanitizer,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddHtmlBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            html="<p>new</p>",
        ),
    )
    fake_html_sanitizer.sanitize.assert_called_once_with("<p>new</p>")
    fake_block_gateway.add_html.assert_awaited_once()
    saved = fake_block_gateway.add_html.call_args.args[0]
    assert isinstance(saved, HtmlBlock)
    assert saved.oid == oid
    assert saved.position == 1
    assert saved.html.value == "<p>new</p>"
    fake_transaction.commit.assert_awaited_once()


async def test_add_html_block_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    other_user_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=course_product.oid,
        permission="edit_lessons",
    )
    handler = AddHtmlBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        html_sanitizer=fake_html_sanitizer,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddHtmlBlockCommand(
                actor_id=other_user_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                html="<p>x</p>",
            ),
        )
    fake_block_gateway.add_html.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


# ---- add_katex ----


async def test_add_katex_block_appends_at_next_position(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = []
    handler = AddKatexBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddKatexBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            source=r"E=mc^2",
        ),
    )
    fake_block_gateway.add_katex.assert_awaited_once()
    saved = fake_block_gateway.add_katex.call_args.args[0]
    assert isinstance(saved, KatexBlock)
    assert saved.oid == oid
    assert saved.position == 0
    assert saved.source.value == r"E=mc^2"
    fake_transaction.commit.assert_awaited_once()


# ---- update_html ----


async def test_update_html_block_replaces_body(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateHtmlBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        html_sanitizer=fake_html_sanitizer,
        event_bus=fake_event_bus,
    )
    await handler.run(
        UpdateHtmlBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(html_block.oid),
            html="<p>new</p>",
        ),
    )
    assert html_block.html.value == "<p>new</p>"
    fake_block_gateway.update_html.assert_awaited_once_with(html_block)
    fake_transaction.commit.assert_awaited_once()


async def test_update_html_block_wrong_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    latex_block: KatexBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = latex_block
    handler = UpdateHtmlBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        html_sanitizer=fake_html_sanitizer,
        event_bus=fake_event_bus,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            UpdateHtmlBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(latex_block.oid),
                html="<p>x</p>",
            ),
        )
    fake_block_gateway.update_html.assert_not_awaited()


# ---- update_katex ----


async def test_update_katex_block_replaces_source(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    latex_block: KatexBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = latex_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateKatexBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        UpdateKatexBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(latex_block.oid),
            source=r"a^2 + b^2",
        ),
    )
    assert latex_block.source.value == r"a^2 + b^2"
    fake_block_gateway.update_katex.assert_awaited_once_with(latex_block)


async def test_update_katex_block_wrong_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    handler = UpdateKatexBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            UpdateKatexBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
                source="x",
            ),
        )


# ---- reorder ----


async def test_reorder_blocks_calls_gateway(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    html_block: HtmlBlock,
    latex_block: KatexBlock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = [html_block, latex_block]
    handler = ReorderLessonBlocksCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        ReorderLessonBlocksCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            ordered_ids=[
                LessonBlockID(latex_block.oid),
                LessonBlockID(html_block.oid),
            ],
        ),
    )
    fake_block_gateway.reorder.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_reorder_blocks_mismatch_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = [html_block]
    handler = ReorderLessonBlocksCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InvalidReorderError):
        await handler.run(
            ReorderLessonBlocksCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                ordered_ids=[LessonBlockID(uuid.uuid4())],
            ),
        )
    fake_block_gateway.reorder.assert_not_awaited()


# ---- add_rutube_video ----


_VALID_RUTUBE_URL = "https://rutube.ru/video/f9bb1e0bdfac28c93c2c35a45f87f3eb/"


async def test_add_rutube_video_block_extracts_id_from_url(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = []
    handler = AddRutubeVideoBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    oid = await handler.run(
        AddRutubeVideoBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            rutube_url=_VALID_RUTUBE_URL,
            title="Lecture 1",
        ),
    )
    fake_block_gateway.add_rutube_video.assert_awaited_once()
    saved = fake_block_gateway.add_rutube_video.call_args.args[0]
    assert isinstance(saved, RutubeVideoBlock)
    assert saved.oid == oid
    assert saved.position == 0
    assert saved.external_id.value == "f9bb1e0bdfac28c93c2c35a45f87f3eb"
    assert saved.title is not None
    assert saved.title.value == "Lecture 1"
    fake_transaction.commit.assert_awaited_once()


async def test_add_rutube_video_block_invalid_url_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    from learnic.entities.course_block.errors import InvalidRutubeUrlError

    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    handler = AddRutubeVideoBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InvalidRutubeUrlError):
        await handler.run(
            AddRutubeVideoBlockCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                rutube_url="https://youtube.com/watch?v=abc",
            ),
        )
    fake_block_gateway.add_rutube_video.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


# ---- update_rutube_video ----


async def test_update_rutube_video_block_replaces_url_and_title(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    rutube_video_block: RutubeVideoBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = rutube_video_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateRutubeVideoBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    new_url = "https://rutube.ru/video/0123456789abcdef0123456789abcdef/"
    await handler.run(
        UpdateRutubeVideoBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(rutube_video_block.oid),
            rutube_url=new_url,
            title="New Caption",
        ),
    )
    assert rutube_video_block.external_id.value == ("0123456789abcdef0123456789abcdef")
    assert rutube_video_block.title is not None
    assert rutube_video_block.title.value == "New Caption"
    fake_block_gateway.update_rutube_video.assert_awaited_once_with(
        rutube_video_block,
    )
    fake_transaction.commit.assert_awaited_once()


async def test_update_rutube_video_block_clears_title_with_none(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    rutube_video_block: RutubeVideoBlock,
    author_id: UserID,
) -> None:
    from learnic.entities.course_block.value_objects import VideoTitle

    rutube_video_block.update_title(VideoTitle("had caption"))
    fake_block_gateway.with_id.return_value = rutube_video_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateRutubeVideoBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        UpdateRutubeVideoBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(rutube_video_block.oid),
            rutube_url=_VALID_RUTUBE_URL,
            title=None,
        ),
    )
    assert rutube_video_block.title is None


async def test_update_rutube_video_block_wrong_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    handler = UpdateRutubeVideoBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            UpdateRutubeVideoBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(html_block.oid),
                rutube_url=_VALID_RUTUBE_URL,
                title=None,
            ),
        )


# ---- delete ----


async def test_delete_block_calls_gateway(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    fake_product_gateway.with_id.return_value = course_product
    handler = DeleteLessonBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    await handler.run(
        DeleteLessonBlockCommand(
            actor_id=author_id,
            block_id=LessonBlockID(html_block.oid),
        ),
    )
    fake_block_gateway.delete.assert_awaited_once_with(html_block.oid)
    fake_transaction.commit.assert_awaited_once()


async def test_delete_block_missing_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = None
    handler = DeleteLessonBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            DeleteLessonBlockCommand(
                actor_id=author_id,
                block_id=LessonBlockID(uuid.uuid4()),
            ),
        )


# ---- add_code ----


_NPM_TAB = CodeTabInput(label="npm", source="npm i react", language="bash")
_PNPM_TAB = CodeTabInput(label="pnpm", source="pnpm add react", language="bash")
_PLAIN_TS_TAB = CodeTabInput(label="", source="const x = 1;", language="ts")


async def test_add_code_block_appends_multi_tab_at_next_position(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    code_block: CodeBlock,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = [code_block]
    handler = AddCodeBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddCodeBlockCommand(
            actor_id=author_id,
            lesson_id=CourseLessonID(course_lesson.oid),
            tabs=(_NPM_TAB, _PNPM_TAB),
        ),
    )
    fake_block_gateway.add_code.assert_awaited_once()
    saved = fake_block_gateway.add_code.call_args.args[0]
    assert isinstance(saved, CodeBlock)
    assert saved.oid == oid
    assert saved.position == code_block.position + 1
    assert [t.label.value for t in saved.tabs] == ["npm", "pnpm"]
    assert [t.language.value for t in saved.tabs] == ["bash", "bash"]
    fake_transaction.commit.assert_awaited_once()


async def test_add_code_block_rejects_unsupported_language(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = []
    handler = AddCodeBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(UnsupportedCodeLanguageError):
        await handler.run(
            AddCodeBlockCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                tabs=(
                    CodeTabInput(label="", source="x", language="haskell"),
                ),
            ),
        )
    fake_block_gateway.add_code.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


async def test_add_code_block_rejects_duplicate_labels(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_lesson_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_lesson: CourseLesson,
    author_id: UserID,
) -> None:
    fake_lesson_gateway.with_id.return_value = course_lesson
    fake_product_gateway.with_id.return_value = course_product
    fake_block_gateway.list_for_lesson.return_value = []
    handler = AddCodeBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        lesson_gateway=fake_lesson_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(DuplicateCodeTabLabelError):
        await handler.run(
            AddCodeBlockCommand(
                actor_id=author_id,
                lesson_id=CourseLessonID(course_lesson.oid),
                tabs=(
                    _NPM_TAB,
                    CodeTabInput(label="npm", source="x", language="bash"),
                ),
            ),
        )
    fake_block_gateway.add_code.assert_not_awaited()


# ---- update_code ----


async def test_update_code_block_replaces_tabs(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    code_block: CodeBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = code_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateCodeBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateCodeBlockCommand(
            actor_id=author_id,
            block_id=code_block.oid,
            tabs=(_NPM_TAB, _PNPM_TAB),
        ),
    )
    fake_block_gateway.update_code.assert_awaited_once_with(code_block)
    assert [t.label.value for t in code_block.tabs] == ["npm", "pnpm"]
    fake_transaction.commit.assert_awaited_once()


async def test_update_code_block_wrong_type_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_block_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    html_block: HtmlBlock,
    author_id: UserID,
) -> None:
    fake_block_gateway.with_id.return_value = html_block
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateCodeBlockCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        block_gateway=fake_block_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(WrongBlockTypeError):
        await handler.run(
            UpdateCodeBlockCommand(
                actor_id=author_id,
                block_id=html_block.oid,
                tabs=(_PLAIN_TS_TAB,),
            ),
        )
    fake_block_gateway.update_code.assert_not_awaited()
    fake_transaction.commit.assert_not_called()

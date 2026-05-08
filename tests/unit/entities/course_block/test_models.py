import uuid

from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.models import (
    HtmlBlock,
    KatexBlock,
    RutubeVideoBlock,
)
from learnic.entities.course_block.value_objects import (
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.product.ids import ProductID


_VALID_ID = "f9bb1e0bdfac28c93c2c35a45f87f3eb"
_OTHER_ID = "0123456789abcdef0123456789abcdef"


def _lesson_id() -> CourseLessonID:
    return CourseLessonID(uuid.uuid4())


def _product_id() -> ProductID:
    return ProductID(uuid.uuid4())


class TestHtmlBlock:
    def test_create_initial_state(self) -> None:
        b = HtmlBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            html=HtmlContent("<p>hi</p>"),
            position=0,
        )
        assert b.html.value == "<p>hi</p>"
        assert b.position == 0
        assert b.type is BlockType.HTML

    def test_update_html(self) -> None:
        b = HtmlBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            html=HtmlContent("<p>old</p>"),
            position=0,
        )
        b.update_html(HtmlContent("<p>new</p>"))
        assert b.html.value == "<p>new</p>"

    def test_change_position(self) -> None:
        b = HtmlBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            html=HtmlContent("<p>x</p>"),
            position=0,
        )
        b.change_position(7)
        assert b.position == 7


class TestKatexBlock:
    def test_create_initial_state(self) -> None:
        b = KatexBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            source=KatexSource(r"E=mc^2"),
            position=0,
        )
        assert b.source.value == r"E=mc^2"
        assert b.type is BlockType.KATEX

    def test_update_source(self) -> None:
        b = KatexBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            source=KatexSource("a"),
            position=0,
        )
        b.update_source(KatexSource("b"))
        assert b.source.value == "b"


class TestRutubeVideoBlock:
    def test_create_initial_state(self) -> None:
        b = RutubeVideoBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            external_id=RutubeVideoID(_VALID_ID),
            position=0,
            title=VideoTitle("Lecture 1"),
        )
        assert b.external_id.value == _VALID_ID
        assert b.type is BlockType.RUTUBE_VIDEO
        assert b.title is not None
        assert b.title.value == "Lecture 1"

    def test_create_without_title(self) -> None:
        b = RutubeVideoBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            external_id=RutubeVideoID(_VALID_ID),
            position=0,
        )
        assert b.title is None

    def test_update_external_id(self) -> None:
        b = RutubeVideoBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            external_id=RutubeVideoID(_VALID_ID),
            position=0,
        )
        b.update_external_id(RutubeVideoID(_OTHER_ID))
        assert b.external_id.value == _OTHER_ID

    def test_update_title_set_then_clear(self) -> None:
        b = RutubeVideoBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            external_id=RutubeVideoID(_VALID_ID),
            position=0,
        )
        b.update_title(VideoTitle("Caption"))
        assert b.title is not None
        b.update_title(None)
        assert b.title is None

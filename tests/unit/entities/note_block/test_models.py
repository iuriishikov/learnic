import uuid

import pytest

from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.errors import (
    CorrectOptionNotInOptionsError,
    CorrectOptionsNotSubsetError,
    DuplicateAcceptedAnswerError,
    DuplicateChoiceOptionLabelError,
    DuplicateCodeTabLabelError,
    EmptyCodeTabsError,
    EmptyCorrectOptionsError,
    TooFewAcceptedAnswersError,
    TooFewChoiceOptionsError,
    TooManyAcceptedAnswersError,
    TooManyChoiceOptionsError,
    TooManyCodeTabsError,
)
from learnic.entities.note_block.ids import ChoiceOptionID
from learnic.entities.note_block.models import (
    ChoiceOption,
    CodeBlock,
    CodeTab,
    HtmlBlock,
    KatexBlock,
    MultiChoiceBlock,
    RutubeVideoBlock,
    SingleChoiceBlock,
    TextInputBlock,
)
from learnic.entities.note_block.value_objects import (
    AcceptedAnswer,
    ChoiceOptionLabel,
    CodeLanguage,
    CodeSource,
    CodeTabLabel,
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.product.ids import ProductID


_VALID_ID = "f9bb1e0bdfac28c93c2c35a45f87f3eb"
_OTHER_ID = "0123456789abcdef0123456789abcdef"


def _lesson_id() -> NoteLessonID:
    return NoteLessonID(uuid.uuid4())


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


def _tab(label: str, source: str, language: str) -> CodeTab:
    return CodeTab(
        label=CodeTabLabel(label),
        source=CodeSource(source),
        language=CodeLanguage(language),
    )


class TestCodeBlock:
    def test_create_single_tab_with_empty_label(self) -> None:
        b = CodeBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            tabs=[_tab("", "const x = 1;\n", "ts")],
            position=0,
        )
        assert len(b.tabs) == 1
        assert b.tabs[0].source.value == "const x = 1;\n"
        assert b.tabs[0].language.value == "ts"
        assert b.position == 0
        assert b.type is BlockType.CODE

    def test_create_multi_tab(self) -> None:
        b = CodeBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            tabs=[
                _tab("npm", "npm i react", "bash"),
                _tab("pnpm", "pnpm add react", "bash"),
                _tab("yarn", "yarn add react", "bash"),
            ],
            position=0,
        )
        assert [t.label.value for t in b.tabs] == ["npm", "pnpm", "yarn"]

    def test_replace_tabs(self) -> None:
        b = CodeBlock.create(
            lesson_id=_lesson_id(),
            product_id=_product_id(),
            tabs=[_tab("", "a", "plain")],
            position=0,
        )
        b.replace_tabs([_tab("", "b", "bash")])
        assert b.tabs[0].source.value == "b"
        assert b.tabs[0].language.value == "bash"

    def test_rejects_empty_tabs(self) -> None:
        with pytest.raises(EmptyCodeTabsError):
            CodeBlock.create(
                lesson_id=_lesson_id(),
                product_id=_product_id(),
                tabs=[],
                position=0,
            )

    def test_rejects_duplicate_labels(self) -> None:
        with pytest.raises(DuplicateCodeTabLabelError):
            CodeBlock.create(
                lesson_id=_lesson_id(),
                product_id=_product_id(),
                tabs=[
                    _tab("npm", "x", "bash"),
                    _tab("npm", "y", "bash"),
                ],
                position=0,
            )

    def test_rejects_empty_label_in_multi_tab(self) -> None:
        with pytest.raises(DuplicateCodeTabLabelError):
            CodeBlock.create(
                lesson_id=_lesson_id(),
                product_id=_product_id(),
                tabs=[
                    _tab("", "x", "bash"),
                    _tab("pnpm", "y", "bash"),
                ],
                position=0,
            )

    def test_rejects_too_many_tabs(self) -> None:
        with pytest.raises(TooManyCodeTabsError):
            CodeBlock.create(
                lesson_id=_lesson_id(),
                product_id=_product_id(),
                tabs=[_tab(f"t{i}", "x", "plain") for i in range(9)],
                position=0,
            )


def _option(label: str) -> ChoiceOption:
    return ChoiceOption.create(ChoiceOptionLabel(label))


def _make_single(
    options: list[ChoiceOption],
    correct: ChoiceOptionID,
) -> SingleChoiceBlock:
    return SingleChoiceBlock.create(
        lesson_id=_lesson_id(),
        product_id=_product_id(),
        options=options,
        correct_option_id=correct,
        position=0,
    )


def _make_multi(
    options: list[ChoiceOption],
    correct: frozenset[ChoiceOptionID],
) -> MultiChoiceBlock:
    return MultiChoiceBlock.create(
        lesson_id=_lesson_id(),
        product_id=_product_id(),
        options=options,
        correct_option_ids=correct,
        position=0,
    )


class TestSingleChoiceBlock:
    def test_create_initial_state(self) -> None:
        a, b = _option("Yes"), _option("No")
        block = _make_single([a, b], a.oid)
        assert block.type is BlockType.SINGLE_CHOICE
        assert [o.label.value for o in block.options] == ["Yes", "No"]
        assert block.correct_option_id == a.oid

    def test_check_correct(self) -> None:
        a, b = _option("A"), _option("B")
        assert _make_single([a, b], a.oid).check(a.oid) is True

    def test_check_incorrect(self) -> None:
        a, b = _option("A"), _option("B")
        assert _make_single([a, b], a.oid).check(b.oid) is False

    def test_check_unknown_id(self) -> None:
        # Unknown ids are simply incorrect — not an error. The
        # student may have crafted the payload; we don't leak.
        a, b = _option("A"), _option("B")
        assert (
            _make_single([a, b], a.oid).check(ChoiceOptionID(uuid.uuid4())) is False
        )

    def test_rejects_too_few_options(self) -> None:
        a = _option("only")
        with pytest.raises(TooFewChoiceOptionsError):
            _make_single([a], a.oid)

    def test_rejects_too_many_options(self) -> None:
        opts = [_option(f"opt-{i}") for i in range(9)]
        with pytest.raises(TooManyChoiceOptionsError):
            _make_single(opts, opts[0].oid)

    def test_rejects_duplicate_labels(self) -> None:
        a = ChoiceOption.create(ChoiceOptionLabel("same"))
        b = ChoiceOption.create(ChoiceOptionLabel("same"))
        with pytest.raises(DuplicateChoiceOptionLabelError):
            _make_single([a, b], a.oid)

    def test_accepts_empty_placeholder_labels(self) -> None:
        # Freshly created blocks ship with empty placeholder
        # options — dedup must skip them so two unfilled rows can
        # coexist until the author types real labels.
        a = ChoiceOption.create(ChoiceOptionLabel(""))
        b = ChoiceOption.create(ChoiceOptionLabel(""))
        block = _make_single([a, b], a.oid)
        assert [o.label.value for o in block.options] == ["", ""]

    def test_rejects_correct_not_in_options(self) -> None:
        a, b = _option("A"), _option("B")
        with pytest.raises(CorrectOptionNotInOptionsError):
            _make_single([a, b], ChoiceOptionID(uuid.uuid4()))

    def test_replace_options_atomic(self) -> None:
        a, b = _option("A"), _option("B")
        block = _make_single([a, b], a.oid)
        c, d = _option("C"), _option("D")
        block.replace_options([c, d], d.oid)
        assert block.correct_option_id == d.oid
        assert [o.label.value for o in block.options] == ["C", "D"]

    def test_replace_options_rejects_mismatched_correct(self) -> None:
        a, b = _option("A"), _option("B")
        block = _make_single([a, b], a.oid)
        c, d = _option("C"), _option("D")
        with pytest.raises(CorrectOptionNotInOptionsError):
            block.replace_options([c, d], a.oid)


class TestMultiChoiceBlock:
    def test_create_initial_state(self) -> None:
        a, b, c = _option("A"), _option("B"), _option("C")
        block = _make_multi([a, b, c], frozenset({a.oid, c.oid}))
        assert block.type is BlockType.MULTI_CHOICE
        assert block.correct_option_ids == frozenset({a.oid, c.oid})

    def test_check_correct_exact_match(self) -> None:
        a, b, c = _option("A"), _option("B"), _option("C")
        block = _make_multi([a, b, c], frozenset({a.oid, c.oid}))
        assert block.check(frozenset({a.oid, c.oid})) is True
        # Order/insertion shouldn't matter — frozenset semantics.
        assert block.check(frozenset({c.oid, a.oid})) is True

    def test_check_missing_one(self) -> None:
        a, b, c = _option("A"), _option("B"), _option("C")
        block = _make_multi([a, b, c], frozenset({a.oid, c.oid}))
        assert block.check(frozenset({a.oid})) is False

    def test_check_extra(self) -> None:
        a, b, c = _option("A"), _option("B"), _option("C")
        block = _make_multi([a, b, c], frozenset({a.oid, c.oid}))
        assert block.check(frozenset({a.oid, b.oid, c.oid})) is False

    def test_check_empty(self) -> None:
        a, b = _option("A"), _option("B")
        assert _make_multi([a, b], frozenset({a.oid})).check(frozenset()) is False

    def test_rejects_empty_correct_set(self) -> None:
        a, b = _option("A"), _option("B")
        with pytest.raises(EmptyCorrectOptionsError):
            _make_multi([a, b], frozenset())

    def test_rejects_correct_not_subset(self) -> None:
        a, b = _option("A"), _option("B")
        rogue = ChoiceOptionID(uuid.uuid4())
        with pytest.raises(CorrectOptionsNotSubsetError):
            _make_multi([a, b], frozenset({a.oid, rogue}))


def _make_text(
    answers: list[str],
    *,
    case_sensitive: bool = False,
    trim_whitespace: bool = True,
) -> TextInputBlock:
    return TextInputBlock.create(
        lesson_id=_lesson_id(),
        product_id=_product_id(),
        accepted_answers=[AcceptedAnswer(a) for a in answers],
        case_sensitive=case_sensitive,
        trim_whitespace=trim_whitespace,
        position=0,
    )


class TestTextInputBlock:
    def test_create_initial_state(self) -> None:
        block = _make_text(["Paris", "paris"], case_sensitive=True)
        assert block.type is BlockType.TEXT_INPUT
        assert [a.value for a in block.accepted_answers] == ["Paris", "paris"]
        assert block.case_sensitive is True
        assert block.trim_whitespace is True

    def test_check_exact_match(self) -> None:
        assert _make_text(["Paris"], case_sensitive=True).check("Paris") is True

    def test_check_case_insensitive_default(self) -> None:
        block = _make_text(["Paris"])
        assert block.check("paris") is True
        assert block.check("PARIS") is True

    def test_check_case_sensitive_rejects(self) -> None:
        block = _make_text(["Paris"], case_sensitive=True)
        assert block.check("paris") is False

    def test_check_trims_whitespace_when_flag_on(self) -> None:
        block = _make_text(["Paris"])  # trim_whitespace=True default
        assert block.check("  Paris  ") is True

    def test_check_does_not_trim_when_flag_off(self) -> None:
        block = _make_text(["Paris"], trim_whitespace=False)
        assert block.check("  Paris  ") is False
        assert block.check("Paris") is True

    def test_check_picks_any_synonym(self) -> None:
        block = _make_text(["Paris", "Paname"])
        assert block.check("paname") is True

    def test_check_empty(self) -> None:
        assert _make_text(["Paris"]).check("") is False

    def test_rejects_zero_accepted(self) -> None:
        with pytest.raises(TooFewAcceptedAnswersError):
            TextInputBlock.create(
                lesson_id=_lesson_id(),
                product_id=_product_id(),
                accepted_answers=[],
                case_sensitive=False,
                trim_whitespace=True,
                position=0,
            )

    def test_rejects_too_many_accepted(self) -> None:
        with pytest.raises(TooManyAcceptedAnswersError):
            _make_text([f"answer-{i}" for i in range(11)])

    def test_rejects_duplicates_under_normalisation(self) -> None:
        # "Paris" and " paris " collide under default flags
        # (case-insensitive, trim) — surface as duplicate so the
        # author doesn't ship a phantom "alternative".
        with pytest.raises(DuplicateAcceptedAnswerError):
            _make_text(["Paris", " paris "])

    def test_accepts_empty_placeholder_answers(self) -> None:
        # Freshly created blocks ship with placeholder answers —
        # dedup must skip empty/blank rows so the author can leave
        # them unfilled until they type real values.
        block = _make_text(["", "   ", "Paris"])
        assert [a.value for a in block.accepted_answers] == ["", "   ", "Paris"]

    def test_allows_distinct_under_case_sensitive(self) -> None:
        # Same strings with different case are distinct when
        # case_sensitive=True.
        block = _make_text(["Paris", "paris"], case_sensitive=True)
        assert len(block.accepted_answers) == 2

    def test_replace_answers_atomic(self) -> None:
        block = _make_text(["Paris"])
        block.replace_answers(
            [AcceptedAnswer("London"), AcceptedAnswer("LONDON")],
            case_sensitive=True,
            trim_whitespace=False,
        )
        assert block.case_sensitive is True
        assert block.trim_whitespace is False
        assert [a.value for a in block.accepted_answers] == ["London", "LONDON"]

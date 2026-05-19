import pytest

from learnic.entities.product.constants import (
    DESCRIPTION_MAX_LEN,
    DURATION_HOURS_MAX,
    DURATION_HOURS_MIN,
    QA_ANSWER_MAX_LEN,
    QA_QUESTION_MAX_LEN,
    TITLE_MAX_LEN,
)
from learnic.entities.product.errors import (
    EmptyProductFieldError,
    ProductDurationOutOfRangeError,
    ProductFieldTooLongError,
)
from learnic.entities.product.value_objects import (
    DurationHours,
    ProductDescription,
    ProductTitle,
    QAAnswer,
    QAQuestion,
)


class TestProductTitle:
    def test_accepts_valid(self) -> None:
        assert ProductTitle("Hello").value == "Hello"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyProductFieldError) as exc:
            ProductTitle("   ")
        assert exc.value.field == "name"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ProductFieldTooLongError):
            ProductTitle("x" * (TITLE_MAX_LEN + 1))


class TestProductDescription:
    def test_accepts_valid_html(self) -> None:
        assert ProductDescription("<p>ok</p>").value == "<p>ok</p>"

    def test_rejects_empty(self) -> None:
        with pytest.raises(EmptyProductFieldError):
            ProductDescription("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ProductFieldTooLongError):
            ProductDescription("x" * (DESCRIPTION_MAX_LEN + 1))


class TestDurationHours:
    def test_accepts_min(self) -> None:
        assert DurationHours(DURATION_HOURS_MIN).value == DURATION_HOURS_MIN

    def test_accepts_max(self) -> None:
        assert DurationHours(DURATION_HOURS_MAX).value == DURATION_HOURS_MAX

    @pytest.mark.parametrize(
        "value",
        [DURATION_HOURS_MIN - 1, DURATION_HOURS_MAX + 1, 0, -1],
    )
    def test_rejects_out_of_range(self, value: int) -> None:
        with pytest.raises(ProductDurationOutOfRangeError):
            DurationHours(value)


class TestQAQuestion:
    def test_accepts_valid(self) -> None:
        assert QAQuestion("Why?").value == "Why?"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyProductFieldError):
            QAQuestion("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ProductFieldTooLongError):
            QAQuestion("x" * (QA_QUESTION_MAX_LEN + 1))


class TestQAAnswer:
    def test_accepts_valid(self) -> None:
        assert QAAnswer("Because.").value == "Because."

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyProductFieldError):
            QAAnswer("\n\t ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ProductFieldTooLongError):
            QAAnswer("x" * (QA_ANSWER_MAX_LEN + 1))

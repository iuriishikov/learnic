import pytest

from learnic.entities.product.constants import (
    ACCESS_WINDOW_MINUTES_MAX,
    DESCRIPTION_MAX_LEN,
    DURATION_HOURS_MAX,
    DURATION_HOURS_MIN,
    QA_ANSWER_MAX_LEN,
    QA_QUESTION_MAX_LEN,
    STREAM_URL_MAX_LEN,
    TITLE_MAX_LEN,
    WEBINAR_DURATION_MINUTES_MAX,
    WEBINAR_LESSONS_MAX,
    WEBINAR_PARTICIPANTS_MIN,
)
from learnic.entities.product.errors import (
    EmptyProductFieldError,
    InvalidAccessWindowError,
    InvalidParticipantsLimitError,
    InvalidStreamUrlError,
    InvalidWebinarDurationError,
    InvalidWebinarLessonsError,
    ProductDurationOutOfRangeError,
    ProductFieldTooLongError,
)
from learnic.entities.product.value_objects import (
    AccessWindow,
    DurationHours,
    ParticipantsLimit,
    ProductDescription,
    ProductTitle,
    QAAnswer,
    QAQuestion,
    StreamUrl,
    WebinarLessonsCount,
    WebinarSessionDuration,
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


class TestWebinarLessonsCount:
    def test_accepts_min(self) -> None:
        assert WebinarLessonsCount(1).value == 1

    def test_accepts_max(self) -> None:
        assert WebinarLessonsCount(WEBINAR_LESSONS_MAX).value == WEBINAR_LESSONS_MAX

    @pytest.mark.parametrize("value", [0, -1, WEBINAR_LESSONS_MAX + 1])
    def test_rejects_out_of_range(self, value: int) -> None:
        with pytest.raises(InvalidWebinarLessonsError):
            WebinarLessonsCount(value)


class TestParticipantsLimit:
    def test_accepts_min(self) -> None:
        assert (
            ParticipantsLimit(WEBINAR_PARTICIPANTS_MIN).value
            == WEBINAR_PARTICIPANTS_MIN
        )

    def test_rejects_below_min(self) -> None:
        with pytest.raises(InvalidParticipantsLimitError):
            ParticipantsLimit(0)


class TestWebinarSessionDuration:
    def test_accepts_typical(self) -> None:
        assert WebinarSessionDuration(60).value == 60

    @pytest.mark.parametrize(
        "value",
        [0, -1, WEBINAR_DURATION_MINUTES_MAX + 1],
    )
    def test_rejects_out_of_range(self, value: int) -> None:
        with pytest.raises(InvalidWebinarDurationError):
            WebinarSessionDuration(value)


class TestAccessWindow:
    def test_accepts_zero(self) -> None:
        assert AccessWindow(0).value == 0

    def test_accepts_max(self) -> None:
        assert (
            AccessWindow(ACCESS_WINDOW_MINUTES_MAX).value == ACCESS_WINDOW_MINUTES_MAX
        )

    @pytest.mark.parametrize(
        "value",
        [-1, ACCESS_WINDOW_MINUTES_MAX + 1],
    )
    def test_rejects_out_of_range(self, value: int) -> None:
        with pytest.raises(InvalidAccessWindowError):
            AccessWindow(value)


class TestStreamUrl:
    def test_accepts_https(self) -> None:
        url = StreamUrl("https://meet.example.com/x")
        assert url.value == "https://meet.example.com/x"

    def test_accepts_http(self) -> None:
        url = StreamUrl("http://meet.example.com/x")
        assert url.value == "http://meet.example.com/x"

    def test_rejects_blank(self) -> None:
        with pytest.raises(InvalidStreamUrlError) as exc:
            StreamUrl("   ")
        assert exc.value.reason == "empty"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidStreamUrlError) as exc:
            StreamUrl("https://" + "x" * STREAM_URL_MAX_LEN)
        assert exc.value.reason == "too_long"

    def test_rejects_invalid_scheme(self) -> None:
        with pytest.raises(InvalidStreamUrlError) as exc:
            StreamUrl("ftp://example.com/x")
        assert exc.value.reason == "invalid_scheme"

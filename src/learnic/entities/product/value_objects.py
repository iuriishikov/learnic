from learnic.entities.common.value_object import ValueObject
from learnic.entities.product.constants import (
    ACCESS_WINDOW_MINUTES_MAX,
    ACCESS_WINDOW_MINUTES_MIN,
    DESCRIPTION_MAX_LEN,
    DURATION_HOURS_MAX,
    DURATION_HOURS_MIN,
    QA_ANSWER_MAX_LEN,
    QA_QUESTION_MAX_LEN,
    STREAM_URL_MAX_LEN,
    TITLE_MAX_LEN,
    WEBINAR_DURATION_MINUTES_MAX,
    WEBINAR_DURATION_MINUTES_MIN,
    WEBINAR_LESSONS_MAX,
    WEBINAR_LESSONS_MIN,
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


class ProductTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyProductFieldError("name")
        if len(self.value) > TITLE_MAX_LEN:
            raise ProductFieldTooLongError("name", TITLE_MAX_LEN)


class ProductDescription(ValueObject):
    """Sanitized HTML description.

    The VO enforces only length/emptiness invariants; HTML
    sanitization happens in the command handler via the
    ``HtmlSanitizer`` Protocol before the VO is constructed.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise EmptyProductFieldError("description")
        if len(self.value) > DESCRIPTION_MAX_LEN:
            raise ProductFieldTooLongError("description", DESCRIPTION_MAX_LEN)


class DurationHours(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value < DURATION_HOURS_MIN or self.value > DURATION_HOURS_MAX:
            raise ProductDurationOutOfRangeError(
                "total_duration_in_hours",
                DURATION_HOURS_MIN,
                DURATION_HOURS_MAX,
            )


class QAQuestion(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyProductFieldError("question")
        if len(self.value) > QA_QUESTION_MAX_LEN:
            raise ProductFieldTooLongError(
                "question",
                QA_QUESTION_MAX_LEN,
            )


class QAAnswer(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyProductFieldError("answer")
        if len(self.value) > QA_ANSWER_MAX_LEN:
            raise ProductFieldTooLongError("answer", QA_ANSWER_MAX_LEN)


class WebinarLessonsCount(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value < WEBINAR_LESSONS_MIN or self.value > WEBINAR_LESSONS_MAX:
            raise InvalidWebinarLessonsError(
                WEBINAR_LESSONS_MIN,
                WEBINAR_LESSONS_MAX,
            )


class ParticipantsLimit(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value < WEBINAR_PARTICIPANTS_MIN:
            raise InvalidParticipantsLimitError(WEBINAR_PARTICIPANTS_MIN)


class WebinarSessionDuration(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if (
            self.value < WEBINAR_DURATION_MINUTES_MIN
            or self.value > WEBINAR_DURATION_MINUTES_MAX
        ):
            raise InvalidWebinarDurationError(
                WEBINAR_DURATION_MINUTES_MIN,
                WEBINAR_DURATION_MINUTES_MAX,
            )


class AccessWindow(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if (
            self.value < ACCESS_WINDOW_MINUTES_MIN
            or self.value > ACCESS_WINDOW_MINUTES_MAX
        ):
            raise InvalidAccessWindowError(
                ACCESS_WINDOW_MINUTES_MIN,
                ACCESS_WINDOW_MINUTES_MAX,
            )


class StreamUrl(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidStreamUrlError("empty")
        if len(self.value) > STREAM_URL_MAX_LEN:
            raise InvalidStreamUrlError("too_long")
        if not (self.value.startswith("https://") or self.value.startswith("http://")):
            raise InvalidStreamUrlError("invalid_scheme")

from learnic.entities.common.value_object import ValueObject
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

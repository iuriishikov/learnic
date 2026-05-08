from learnic.entities.common.value_object import ValueObject
from learnic.entities.course_enrollment.constants import (
    PROGRESS_PERCENT_MAX,
    PROGRESS_PERCENT_MIN,
)
from learnic.entities.course_enrollment.errors import (
    InvalidProgressPercentError,
)


class ProgressPercent(ValueObject):
    value: int

    def __post_init__(self) -> None:
        if self.value < PROGRESS_PERCENT_MIN or self.value > PROGRESS_PERCENT_MAX:
            raise InvalidProgressPercentError(
                PROGRESS_PERCENT_MIN,
                PROGRESS_PERCENT_MAX,
            )

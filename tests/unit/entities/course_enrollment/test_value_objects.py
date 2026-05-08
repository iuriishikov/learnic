import pytest

from learnic.entities.course_enrollment.constants import (
    PROGRESS_PERCENT_MAX,
    PROGRESS_PERCENT_MIN,
)
from learnic.entities.course_enrollment.errors import (
    InvalidProgressPercentError,
)
from learnic.entities.course_enrollment.value_objects import (
    ProgressPercent,
)


class TestProgressPercent:
    def test_accepts_min(self) -> None:
        assert ProgressPercent(PROGRESS_PERCENT_MIN).value == PROGRESS_PERCENT_MIN

    def test_accepts_max(self) -> None:
        assert ProgressPercent(PROGRESS_PERCENT_MAX).value == PROGRESS_PERCENT_MAX

    @pytest.mark.parametrize(
        "value",
        [
            PROGRESS_PERCENT_MIN - 1,
            PROGRESS_PERCENT_MAX + 1,
            -10,
            200,
        ],
    )
    def test_rejects_out_of_range(self, value: int) -> None:
        with pytest.raises(InvalidProgressPercentError) as exc:
            ProgressPercent(value)
        assert exc.value.minimum == PROGRESS_PERCENT_MIN
        assert exc.value.maximum == PROGRESS_PERCENT_MAX

import pytest

from learnic.entities.cohort.constants import (
    CANCELLATION_REASON_MAX_LEN,
    COHORT_NAME_MAX_LEN,
    IANA_TIMEZONE_MAX_LEN,
    RECORDING_URL_MAX_LEN,
    RRULE_MAX_LEN,
)
from learnic.entities.cohort.errors import (
    CohortFieldTooLongError,
    EmptyCohortFieldError,
    InvalidIanaTimezoneError,
    InvalidRecordingUrlError,
    InvalidRecurrenceRuleError,
)
from learnic.entities.cohort.value_objects import (
    CancellationReason,
    CohortName,
    IanaTimezone,
    RecordingUrl,
    RecurrenceRule,
)


class TestCohortName:
    def test_accepts_valid(self) -> None:
        assert CohortName("Поток №3").value == "Поток №3"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyCohortFieldError):
            CohortName("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(CohortFieldTooLongError):
            CohortName("x" * (COHORT_NAME_MAX_LEN + 1))


class TestIanaTimezone:
    @pytest.mark.parametrize(
        "name",
        ["UTC", "Europe/Sofia", "America/New_York", "Asia/Tokyo"],
    )
    def test_accepts_known_zones(self, name: str) -> None:
        assert IanaTimezone(name).value == name

    def test_rejects_blank(self) -> None:
        with pytest.raises(InvalidIanaTimezoneError) as exc:
            IanaTimezone("   ")
        assert exc.value.reason == "empty"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidIanaTimezoneError) as exc:
            IanaTimezone("X" * (IANA_TIMEZONE_MAX_LEN + 1))
        assert exc.value.reason == "too_long"

    def test_rejects_unknown_zone(self) -> None:
        with pytest.raises(InvalidIanaTimezoneError) as exc:
            IanaTimezone("Foo/Bar")
        assert exc.value.reason == "not_found"


class TestRecurrenceRule:
    def test_accepts_minimal_freq(self) -> None:
        rule = RecurrenceRule("FREQ=WEEKLY")
        assert rule.value == "FREQ=WEEKLY"

    def test_accepts_complex_rule(self) -> None:
        v = "FREQ=WEEKLY;BYDAY=FR;BYHOUR=19;BYMINUTE=0;UNTIL=20300101T000000Z"
        assert RecurrenceRule(v).value == v

    def test_rejects_blank(self) -> None:
        with pytest.raises(InvalidRecurrenceRuleError) as exc:
            RecurrenceRule("   ")
        assert exc.value.reason == "empty"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidRecurrenceRuleError) as exc:
            RecurrenceRule("FREQ=" + "X" * (RRULE_MAX_LEN + 1))
        assert exc.value.reason == "too_long"

    def test_rejects_missing_freq(self) -> None:
        with pytest.raises(InvalidRecurrenceRuleError) as exc:
            RecurrenceRule("BYDAY=MO")
        assert exc.value.reason == "missing_freq"

    def test_rejects_lowercase_part(self) -> None:
        with pytest.raises(InvalidRecurrenceRuleError) as exc:
            RecurrenceRule("FREQ=WEEKLY;BYDAY=monday")
        assert exc.value.reason == "invalid_part"


class TestCancellationReason:
    def test_accepts_valid(self) -> None:
        assert CancellationReason("Host illness").value == "Host illness"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyCohortFieldError):
            CancellationReason(" \n ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(CohortFieldTooLongError):
            CancellationReason("x" * (CANCELLATION_REASON_MAX_LEN + 1))


class TestRecordingUrl:
    def test_accepts_https(self) -> None:
        u = "https://recordings.example.com/x.mp4"
        assert RecordingUrl(u).value == u

    def test_rejects_blank(self) -> None:
        with pytest.raises(InvalidRecordingUrlError) as exc:
            RecordingUrl("   ")
        assert exc.value.reason == "empty"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidRecordingUrlError) as exc:
            RecordingUrl("https://" + "x" * RECORDING_URL_MAX_LEN)
        assert exc.value.reason == "too_long"

    def test_rejects_invalid_scheme(self) -> None:
        with pytest.raises(InvalidRecordingUrlError) as exc:
            RecordingUrl("ftp://example.com/x.mp4")
        assert exc.value.reason == "invalid_scheme"

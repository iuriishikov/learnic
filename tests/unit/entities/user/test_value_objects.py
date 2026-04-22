import pytest

from learnic.entities.user.constants import (
    PASSWORD_MAX_LEN,
    PASSWORD_MIN_LEN,
)
from learnic.entities.user.errors import (
    InvalidEmailError,
    WeakPasswordError,
)
from learnic.entities.user.value_objects import (
    Email,
    PasswordHash,
    RawPassword,
)


class TestEmail:
    def test_accepts_value_with_at(self) -> None:
        email = Email("user@example.com")
        assert email.value == "user@example.com"

    def test_rejects_value_without_at(self) -> None:
        with pytest.raises(InvalidEmailError):
            Email("no-at-sign")

    def test_rejects_too_long_value(self) -> None:
        too_long = "a" * 320 + "@b"
        with pytest.raises(InvalidEmailError):
            Email(too_long)


class TestRawPassword:
    def test_accepts_min_length(self) -> None:
        password = RawPassword("x" * PASSWORD_MIN_LEN)
        assert password.value == "x" * PASSWORD_MIN_LEN

    def test_rejects_too_short(self) -> None:
        with pytest.raises(WeakPasswordError) as exc:
            RawPassword("x" * (PASSWORD_MIN_LEN - 1))
        assert exc.value.reason == "too_short"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(WeakPasswordError) as exc:
            RawPassword("x" * (PASSWORD_MAX_LEN + 1))
        assert exc.value.reason == "too_long"


class TestPasswordHash:
    def test_accepts_any_non_empty_string(self) -> None:
        # PasswordHash is a storage VO, not validating here.
        ph = PasswordHash("$argon2id$v=19$m=65536,t=3,p=4$abc$xyz")
        assert ph.value.startswith("$argon2id$")

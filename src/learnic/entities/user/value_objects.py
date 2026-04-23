from learnic.entities.common.value_object import ValueObject
from learnic.entities.user.constants import (
    DESCRIPTION_MAX_LEN,
    EMAIL_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PASSWORD_MAX_LEN,
    PASSWORD_MIN_LEN,
    PATRONYMIC_MAX_LEN,
)
from learnic.entities.user.errors import (
    EmptyNameError,
    InvalidDescriptionError,
    InvalidEmailError,
    NameTooLongError,
    WeakPasswordError,
)


class Email(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value or len(self.value) > EMAIL_MAX_LEN:
            raise InvalidEmailError


class FirstName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNameError("first_name")
        if len(self.value) > FIRST_NAME_MAX_LEN:
            raise NameTooLongError("first_name", FIRST_NAME_MAX_LEN)


class LastName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNameError("last_name")
        if len(self.value) > LAST_NAME_MAX_LEN:
            raise NameTooLongError("last_name", LAST_NAME_MAX_LEN)


class Patronymic(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNameError("patronymic")
        if len(self.value) > PATRONYMIC_MAX_LEN:
            raise NameTooLongError("patronymic", PATRONYMIC_MAX_LEN)


class RawPassword(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if len(self.value) < PASSWORD_MIN_LEN:
            raise WeakPasswordError("too_short")
        if len(self.value) > PASSWORD_MAX_LEN:
            raise WeakPasswordError("too_long")


class PasswordHash(ValueObject):
    value: str


class UserDescription(ValueObject):
    """Profile description — already-sanitized HTML.

    The VO enforces only length/emptiness invariants; HTML sanitization
    happens in the command handler via the ``HtmlSanitizer`` Protocol
    before the VO is constructed. To clear the description, set the
    user's ``description`` to ``None`` rather than constructing an
    empty VO.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidDescriptionError(DESCRIPTION_MAX_LEN)
        if len(self.value) > DESCRIPTION_MAX_LEN:
            raise InvalidDescriptionError(DESCRIPTION_MAX_LEN)

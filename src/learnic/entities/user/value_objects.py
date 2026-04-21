from learnic.entities.common.value_object import ValueObject
from learnic.entities.user.constants import (
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PATRONYMIC_MAX_LEN,
)
from learnic.entities.user.errors import EmptyNameError, NameTooLongError


class Email(ValueObject):
    value: str


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

from dataclasses import dataclass

from learnic.entities.common.errors import FieldError


@dataclass(eq=False)
class EmptyNameError(FieldError):
    field: str


@dataclass(eq=False)
class NameTooLongError(FieldError):
    field: str
    limit: int

from learnic.entities.common.errors import FieldError


class EmptyNameError(FieldError):
    field: str


class NameTooLongError(FieldError):
    field: str
    limit: int

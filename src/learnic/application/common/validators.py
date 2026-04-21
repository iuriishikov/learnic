from typing import TypeVar

from learnic.application.common.errors import EntityNotFoundError

T = TypeVar("T")


def validate_empty(value: T | None, entity_id: object) -> T:
    """Raise :class:`EntityNotFoundError` if ``value`` is ``None``.

    Used in query handlers to turn ``None`` from readers into a 404 at
    the HTTP layer via the global exception handler.
    """
    if value is None:
        raise EntityNotFoundError(entity_id)
    return value

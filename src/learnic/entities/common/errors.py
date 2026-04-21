import dataclasses
import inspect
from typing import Any, dataclass_transform


@dataclass_transform(eq_default=False)
class _DomainErrorMeta(type):
    """Metaclass that auto-applies ``@dataclass(eq=False)`` to subclasses.

    Every subclass of :class:`DomainError` that declares fields is
    transparently wrapped so concrete errors state only their data
    carriers and any custom ``__str__``. ``eq=False`` preserves
    :class:`Exception`'s identity-based equality (so errors stay
    hashable and catch-order isn't surprising).

    Subclasses without fields (marker classes like
    :class:`FieldError`) are left untouched.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        if not inspect.get_annotations(cls):
            return cls
        return dataclasses.dataclass(eq=False)(cls)  # type: ignore[arg-type]


class DomainError(Exception, metaclass=_DomainErrorMeta):
    """Base class for all domain-layer errors."""


class FieldError(DomainError):
    """Raised when a value object invariant is violated."""

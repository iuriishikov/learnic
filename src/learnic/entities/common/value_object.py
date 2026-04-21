import dataclasses
from typing import Any, Self, dataclass_transform


@dataclass_transform(frozen_default=True, eq_default=True)
class _ValueObjectMeta(type):
    """Metaclass that auto-applies the standard VO dataclass config.

    Every subclass of :class:`ValueObject` is transparently wrapped
    in ``@dataclass(slots=True, frozen=True, eq=True, unsafe_hash=True)``
    so concrete VOs declare only their fields and invariants.

    The ``__dataclass_fields__`` guard prevents infinite recursion:
    ``dataclass(slots=True, ...)`` creates a new class by calling
    ``type(cls)(name, bases, cls_dict)``, which re-enters this
    metaclass with the already-processed dict — the guard lets
    that pass through unchanged.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        if name == "ValueObject" or "__dataclass_fields__" in namespace:
            return cls
        return dataclasses.dataclass(
            slots=True,
            frozen=True,
            eq=True,
            unsafe_hash=True,
        )(cls)  # type: ignore[arg-type]


class ValueObject(metaclass=_ValueObjectMeta):
    """Base class for single- and multi-attribute value objects.

    Subclasses declare their fields and any invariants via
    ``__post_init__``; the dataclass config (``slots``, ``frozen``,
    ``eq``, ``unsafe_hash``) is applied automatically by the
    metaclass — no per-VO ``@dataclass`` decorator needed.

    Supplies ``__composite_values__`` so VOs can be persisted
    through SQLAlchemy's ``composite()`` without each VO
    restating the serializer. The method returns a tuple of the
    VO's dataclass fields in declaration order — the contract
    SQLAlchemy expects when the composite constructor is a
    callable factory (rather than the VO class itself).
    """

    __slots__ = ()

    def __composite_values__(self) -> tuple[object, ...]:
        return tuple(getattr(self, f.name) for f in dataclasses.fields(self))

    @classmethod
    def of_optional(cls, *values: object) -> Self | None:
        """Construct a VO from possibly-``None`` column values.

        Returns ``None`` when every input is ``None``; otherwise
        forwards the values positionally to the VO constructor
        (which still runs ``__post_init__`` and raises on invalid
        non-null input). Intended as the first argument to
        SQLAlchemy's ``composite()`` for nullable columns — mirrors
        what ``composite.return_none_on`` will do natively in
        SQLAlchemy 2.1.
        """
        if all(v is None for v in values):
            return None
        return cls(*values)

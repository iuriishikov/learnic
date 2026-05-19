from learnic.entities.common.value_object import ValueObject
from learnic.entities.tag.constants import (
    TAG_COLOR_MAX_LEN,
    TAG_NAME_MAX_LEN,
    TAG_NAME_MIN_LEN,
)
from learnic.entities.tag.errors import (
    EmptyTagFieldError,
    TagFieldTooLongError,
)


class TagName(ValueObject):
    """Display name of a tag as the creator typed it.

    Trimmed whitespace counts toward the minimum-length check so
    pure-whitespace input cannot bypass the empty guard. The raw
    untrimmed value is stored — the canonical lookup key is
    :class:`TagSlug`, derived from the same value.
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if len(stripped) < TAG_NAME_MIN_LEN:
            raise EmptyTagFieldError("name")
        if len(self.value) > TAG_NAME_MAX_LEN:
            raise TagFieldTooLongError("name", TAG_NAME_MAX_LEN)


class TagSlug(ValueObject):
    """Normalized lookup key for a tag.

    Produced from :class:`TagName` via :meth:`from_name`. Two tags
    with names that collapse to the same slug are the same tag —
    the unique index on ``tags.slug`` enforces this at the DB
    level. The HTTP boundary never sees this VO; it lives entirely
    in the domain and persistence layers.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise EmptyTagFieldError("slug")
        if len(self.value) > TAG_NAME_MAX_LEN:
            raise TagFieldTooLongError("slug", TAG_NAME_MAX_LEN)

    @classmethod
    def from_name(cls, name: TagName) -> "TagSlug":
        # Cheap-and-deterministic dedup rule: collapse whitespace
        # and case. Unicode-aware ``str.lower()`` covers Cyrillic
        # alongside ASCII; languages with different scripts (e.g.
        # ``Python`` vs ``Питон``) remain distinct, which is
        # intentional — they read differently to humans.
        collapsed = " ".join(name.value.split())
        return cls(collapsed.lower())


class TagColor(ValueObject):
    """Color string in any Pydantic-Color-accepted format.

    The HTTP boundary validates the incoming string via
    ``pydantic.color.Color`` and forwards the canonical
    representation. The VO only enforces non-emptiness and a max
    length wide enough for every accepted form
    (``rgba(255, 255, 255, 0.123)`` is the longest realistic case).
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise EmptyTagFieldError("color")
        if len(self.value) > TAG_COLOR_MAX_LEN:
            raise TagFieldTooLongError("color", TAG_COLOR_MAX_LEN)

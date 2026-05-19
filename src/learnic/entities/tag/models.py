import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.tag.ids import TagID
from learnic.entities.tag.value_objects import TagColor, TagName, TagSlug
from learnic.entities.user.models import UserID


@dataclass
class Tag(BaseEntity[TagID]):
    """A globally-shared name + color attachable to any product.

    Tags are append-only and not scoped to a product or author —
    every authenticated user can create one and every other user
    can reuse it. The lookup key is :class:`TagSlug` (lower-cased,
    whitespace-collapsed ``name``), enforced by a unique index on
    ``tags.slug``. The ``color`` is owned by the first creator and
    immutable thereafter; per-product overrides are intentionally
    not supported.
    """

    name: TagName
    slug: TagSlug
    color: TagColor
    created_by: UserID
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        name: TagName,
        color: TagColor,
        created_by: UserID,
    ) -> Self:
        return cls(
            oid=TagID(uuid.uuid4()),
            name=name,
            slug=TagSlug.from_name(name),
            color=color,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )

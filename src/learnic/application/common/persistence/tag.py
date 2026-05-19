from dataclasses import dataclass
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.entities.product.ids import ProductID
from learnic.entities.tag.ids import TagID
from learnic.entities.tag.models import Tag
from learnic.entities.tag.value_objects import TagSlug


@dataclass(slots=True, frozen=True)
class TagView:
    """Read-side projection of :class:`Tag` for autocomplete and embedding.

    Mirrors what the SPA shows: identifier, display name, color.
    ``created_by`` and ``created_at`` are intentionally absent —
    the tag is global, so authorship is not a UI affordance.
    """

    oid: TagID
    name: str
    color: str


class TagGateway(Protocol):
    """Write-side lookups for :class:`Tag`.

    ``with_slug`` powers the get-or-create branch of
    ``PUT /products/{id}/tags``: the handler first probes by slug,
    creates a new tag only when the slug is unknown. ``with_ids``
    fans out a single SELECT to verify every tag referenced by the
    incoming payload before rewriting the association table.
    """

    async def with_id(self, oid: TagID) -> Tag | None: ...

    async def with_ids(self, oids: list[TagID]) -> list[Tag]: ...

    async def with_slug(self, slug: TagSlug) -> Tag | None: ...


class TagReader(Protocol):
    """Read-side queries returning :class:`TagView` projections."""

    async def search(
        self,
        query: str,
        pagination: Pagination,
    ) -> list[TagView]:
        """Return tags whose name contains ``query`` (case-insensitive).

        Empty ``query`` returns the most-used tags first so the
        SPA's combobox shows something useful on focus. Ordering is
        deterministic so paginated callers do not see duplicates
        across pages.
        """
        ...

    async def for_product(self, product_id: ProductID) -> list[TagView]:
        """Return the product's tags in author-defined order.

        The ``position`` column on ``product_tags`` is the source of
        truth — adapters ``ORDER BY position ASC``.
        """
        ...


class ProductTagsSaver(Protocol):
    """Rewrite the ordered set of tag associations for a product.

    Replaces the entire ``product_tags`` slice for ``product_id``
    in one operation — adapters typically DELETE-then-INSERT inside
    the caller's transaction. Ordering is positional: the input
    list's index becomes the row's ``position``.
    """

    async def replace(
        self,
        product_id: ProductID,
        tag_ids: list[TagID],
    ) -> None: ...

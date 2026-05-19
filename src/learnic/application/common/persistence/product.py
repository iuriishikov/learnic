from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileView
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ProductView:
    """Read-side projection of :class:`Product` returned by the Reader."""

    oid: ProductID
    type: ProductType
    status: ProductStatus
    name: str
    description: str | None
    total_duration_in_hours: int | None
    author: UserRefView
    cover: FileView | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class RecommendationCandidate:
    """A candidate product + raw scoring signals.

    The Reader returns un-normalized counts straight from SQL; the
    query handler does normalization (per-batch max-scale) and
    weighting in Python so the ranking strategy can change without
    a migration or even a server restart (weights come from
    :class:`RecommendationsConfig`).
    """

    view: ProductView
    tag_affinity_raw: float
    author_affinity_raw: float
    popularity_raw: float


class ProductGateway(Protocol):
    """Write-side lookups for :class:`Product`."""

    async def with_id(self, oid: ProductID) -> Product | None: ...

    async def delete(self, product: Product) -> None: ...


class ProductReader(Protocol):
    """Read-side queries returning :class:`ProductView` projections."""

    async def with_id(self, oid: ProductID) -> ProductView | None: ...

    async def accessible_to(
        self,
        user_id: UserID,
        pagination: Pagination,
    ) -> list[ProductView]:
        """Return products the user can access — owned or active collaborations.

        Includes products where ``user_id`` is the author **or** has
        an :class:`CollaborationStatus.ACTIVE` collaboration.
        ``PENDING_INVITE`` and ``REVOKED`` collaborations are excluded.
        """
        ...

    async def published(
        self,
        pagination: Pagination,
    ) -> list[ProductView]: ...

    async def published_count(self) -> int:
        """Return the total number of published products.

        Mirrors ``published(...)``'s WHERE filter without pagination
        so the catalog UI can render numbered page controls. Cheap:
        a single ``COUNT(*)`` against the ``ix_products_type_status``
        index slice.
        """
        ...

    async def search_published_count(self, query: str) -> int:
        """Return the total number of products matching ``query``.

        Mirrors ``search_published(...)``'s WHERE filter (tsvector
        match OR trigram fallback) without pagination. Used to drive
        numbered page controls on the search-mode catalog.
        """
        ...

    async def search_published(
        self,
        query: str,
        pagination: Pagination,
    ) -> list[ProductView]:
        """Search published products by free-text ``query``.

        Multi-field, weighted full-text search across product name
        (weight ``A``), author full name + attached tag names (both
        weight ``B``), and the HTML-stripped description (weight
        ``C``). Morphology is handled by the Russian text-search
        dictionary; typos and transliteration fall through to a
        ``pg_trgm`` similarity fallback over the same concatenated
        text (so "питноо" still finds "питон").

        Results are ranked by a weighted combination of
        ``ts_rank_cd`` and ``similarity`` and tie-broken by
        ``created_at`` desc.

        ``query`` is trimmed/lower-cased inside the adapter; callers
        pass the raw user input. An empty query is invalid here —
        the handler routes empty input to ``published(...)`` instead.
        """
        ...

    async def published_by_author(
        self,
        author_id: UserID,
        pagination: Pagination,
    ) -> list[ProductView]:
        """Published products authored by ``author_id``, newest first.

        Powers the public profile page's "products" section. Excludes
        drafts, archived, and banned products — only ``PUBLISHED`` rows
        are visible to non-author viewers.
        """
        ...

    async def name_exists(
        self,
        author_id: UserID,
        name: str,
        exclude_oid: ProductID | None = None,
    ) -> bool:
        """Return ``True`` if ``author_id`` already owns a product with ``name``.

        Names are unique per author, case-sensitive, across all
        statuses (including archived). Different authors may use
        the same name. Pass ``exclude_oid`` when renaming to skip
        the product being renamed.
        """
        ...

    async def recommendation_candidates(
        self,
        user_id: UserID,
        limit: int,
        popularity_window_days: int,
    ) -> list[RecommendationCandidate]:
        """Return candidate products with raw scoring signals.

        Pools candidates from three sources (UNION'd in one SQL
        query) and emits **un-normalized** counts so the handler
        can blend them with weights:

        - **tag affinity** — how many tags the candidate shares with
          products the user has actively/completed enrolled in.
        - **author affinity** — how many of the candidate's author's
          products the user has actively/completed enrolled in.
        - **popularity** — distinct active/completed enrollments in
          the last ``popularity_window_days`` days; lets the query
          carry cold-start users (no history) and serves as a tie
          breaker for everyone else.

        Always excluded:

        - products authored by ``user_id`` (no self-recommendations),
        - products the user is already enrolled in with status
          ``ACTIVE`` or ``COMPLETED`` (``REFUNDED`` does not exclude —
          the user returned the money, similar offers are still
          relevant),
        - products whose status is not ``PUBLISHED``.

        ``limit`` is an **over-fetch** bound — the handler typically
        passes ``page_size * 3`` so ranking has room to reorder
        before slicing.
        """
        ...

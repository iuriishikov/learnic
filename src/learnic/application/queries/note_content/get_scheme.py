from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseGateway,
    NoteReleaseReader,
    NoteReleaseSchemeView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.enrollment.details import NoteEnrollmentDetails
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetNoteSchemeQuery:
    actor_id: UserID | None
    """``None`` for an anonymous caller (no access cookie)."""
    product_id: ProductID


@final
class GetNoteSchemeQueryHandler:
    """Return the structure-only tree for the current viewer.

    The entry point of the student read flow: the scheme lists the
    lesson ids, whose blocks are then loaded one by one through
    ``GetReleaseLessonQueryHandler``. The projection carries no
    block payloads, so it stays public for **both** visibility
    variants:

        1. Actively-enrolled student → their **pinned** release.
        2. Anyone else viewing a ``PUBLISHED`` note → the **latest**
           release. Unlike the per-lesson block read, ``PRIVATE``
           (invite-only) notes are served too — they are
           catalog-discoverable by design and their landing page
           shows the program; only the block payloads are gated.
        3. Everything else (product missing, not a note, or in a
           non-``PUBLISHED`` state with no active enrollment) →
           ``EntityNotFoundError`` (uniform 404, no reason leak).
    """

    def __init__(
        self,
        product_gateway: ProductGateway,
        enrollment_gateway: EnrollmentGateway,
        release_gateway: NoteReleaseGateway,
        release_reader: NoteReleaseReader,
    ) -> None:
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway
        self._release_gateway: Final = release_gateway
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: GetNoteSchemeQuery,
    ) -> NoteReleaseSchemeView:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None or not product.supports(
            ProductCapability.HAS_NOTE_CONTENT,
        ):
            # Same shape as the per-lesson read: non-note products
            # are hidden under this endpoint family as 404.
            raise EntityNotFoundError(data.product_id)

        release_id = await self._resolve_release_id(product, data.actor_id)
        view = await self._release_reader.get_scheme(release_id)
        if view is None:
            # The chosen release id no longer resolves — invariant
            # violation when it came from an enrollment, a transient
            # race when it came from `latest_for_product`. Surface
            # as 404 so the client can retry.
            raise EntityNotFoundError(release_id)
        return view

    async def _resolve_release_id(
        self,
        product: Product,
        actor_id: UserID | None,
    ) -> NoteReleaseID:
        if actor_id is not None:
            enrollment = (
                await self._enrollment_gateway.with_product_and_student(
                    product.oid,
                    actor_id,
                )
            )
            if (
                enrollment is not None
                and enrollment.status is EnrollmentStatus.ACTIVE
            ):
                # Note-flow gating above guarantees a note
                # enrollment; the gateway hydrates ``details`` from
                # the subtype table.
                assert isinstance(  # noqa: S101
                    enrollment.details,
                    NoteEnrollmentDetails,
                )
                return enrollment.details.release_id

        # Anonymous, signed-out, or not actively enrolled — public
        # path. Only PUBLISHED products are visible; DRAFT/ARCHIVED
        # stay hidden behind 404, same shape as a missing product.
        # No visibility gate: the structure of a PRIVATE note is
        # part of its public catalog page.
        if product.status is not ProductStatus.PUBLISHED:
            raise EntityNotFoundError(product.oid)
        latest = await self._release_gateway.latest_for_product(
            product.oid,
        )
        if latest is None:
            # A PUBLISHED note with zero releases is a transient
            # / invariant-violation state (the first release is
            # what flips the product to PUBLISHED in the first
            # place). Surface as 404.
            raise EntityNotFoundError(product.oid)
        return latest.oid

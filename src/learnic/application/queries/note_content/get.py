from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_release import (
    NoteReleaseContentView,
    NoteReleaseGateway,
    NoteReleaseReader,
)
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.enrollment.details import NoteEnrollmentDetails
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetNoteContentQuery:
    actor_id: UserID | None
    """``None`` for an anonymous caller (no access cookie)."""
    product_id: ProductID


@final
class GetNoteContentQueryHandler:
    """Return the right release content for the current viewer.

    One endpoint, three audiences:

        1. Actively-enrolled student → their **pinned** release.
           Strict pinning still holds — students never auto-upgrade.
        2. Anyone else (anonymous, or signed-in but not enrolled)
           viewing a ``PUBLISHED`` note → the **latest** release
           of the product.
        3. Everything else (product missing, not a note, or in a
           non-``PUBLISHED`` state with no active enrollment) →
           ``EntityNotFoundError``. The 404 is uniform across all
           "no access" cases so the response shape does not leak
           why the caller was rejected.

    Refunded / revoked enrollments fall through to the public
    branch: a note that is still ``PUBLISHED`` stays visible to
    them, just on the latest release instead of their old pin.
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
        data: GetNoteContentQuery,
    ) -> NoteReleaseContentView:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None or not product.supports(
            ProductCapability.HAS_NOTE_CONTENT,
        ):
            # Non-note products are intentionally hidden under
            # the note-content endpoint — surface as 404 rather
            # than leaking kind info via a separate error.
            raise EntityNotFoundError(data.product_id)

        release_id = await self._resolve_release_id(product, data.actor_id)
        view = await self._release_reader.get_content(release_id)
        if view is None:
            # The chosen release id no longer resolves — invariant
            # violation when it came from an enrollment, a transient
            # race when it came from `latest_for_product` (release
            # deleted between the two queries). Either way surface
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

        # Anonymous, signed-out, or not actively enrolled — fall
        # back to the public path. Only PUBLISHED products are
        # visible here; DRAFT/ARCHIVED stay hidden behind
        # 404, same shape as a missing product.
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

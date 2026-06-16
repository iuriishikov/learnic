from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseGateway,
    NoteReleaseReader,
    ReleaseSearchMatch,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.enrollment.details import NoteEnrollmentDetails
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.enums import ProductStatus, ProductVisibility
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID

# Upper bound on matches returned for one query. A sidebar list, not a
# paginated catalog — a single note never has enough content to warrant
# paging, and the SPA shows the best-ranked hits.
NOTE_SEARCH_RESULT_LIMIT: Final = 50


@dataclass(slots=True, frozen=True)
class SearchNoteContentQuery:
    actor_id: UserID | None
    """``None`` for an anonymous caller (no access cookie)."""
    product_id: ProductID
    query: str
    """Free-text query; length is bounded at the HTTP boundary."""


@final
class SearchNoteContentQueryHandler:
    """Full-text search a note's release content for the current viewer.

    Companion of ``GetNoteSchemeQueryHandler`` /
    ``GetReleaseLessonQueryHandler``: the scheme lists the structure,
    this query searches the block payloads. It reuses the **content**
    gate (not the looser scheme gate), so the searchable release is the
    same content the viewer may actually read:

        1. Actively-enrolled student → their **pinned** release.
        2. Author / collaborator with ``READ_PRODUCT`` → the latest
           published release (non-raising permission probe).
        3. Anyone, including anonymous → the latest published release,
           but only when the note is ``PUBLISHED`` **and** ``PUBLIC``.
           A ``PRIVATE`` note's scheme is public yet its content is
           gated — so an outsider searching one gets the same uniform
           404 as the per-lesson read.
        4. Everything else → ``EntityNotFoundError`` (uniform 404).
    """

    def __init__(
        self,
        product_gateway: ProductGateway,
        enrollment_gateway: EnrollmentGateway,
        authorizer: Authorizer,
        release_gateway: NoteReleaseGateway,
        release_reader: NoteReleaseReader,
    ) -> None:
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway
        self._authorizer: Final = authorizer
        self._release_gateway: Final = release_gateway
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: SearchNoteContentQuery,
    ) -> list[ReleaseSearchMatch]:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None or not product.supports(
            ProductCapability.HAS_NOTE_CONTENT,
        ):
            # Non-note products are hidden under this family as 404,
            # matching the scheme / per-lesson reads.
            raise EntityNotFoundError(data.product_id)

        release_id = await self._resolve_accessible_release(
            product,
            data.actor_id,
        )
        return await self._release_reader.search_content(
            release_id,
            data.query,
            NOTE_SEARCH_RESULT_LIMIT,
        )

    async def _resolve_accessible_release(
        self,
        product: Product,
        actor_id: UserID | None,
    ) -> NoteReleaseID:
        if actor_id is not None:
            # Most common viewer first: the enrolled student searching
            # their pinned release.
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
                assert isinstance(  # noqa: S101
                    enrollment.details,
                    NoteEnrollmentDetails,
                )
                return enrollment.details.release_id

            # Author / collaborator: non-raising permission probe so a
            # denial falls through to the open-distribution rule rather
            # than leaking a 403.
            permissions = await self._authorizer.effective_permissions(
                actor_id,
                AuthzTarget.for_product(product.oid),
            )
            if (
                permissions is not None
                and Permission.READ_PRODUCT in permissions
            ):
                return await self._latest_published_release(product)

        # Open distribution: content is searchable only when the note
        # is published AND openly distributed.
        if (
            product.status is ProductStatus.PUBLISHED
            and product.visibility is ProductVisibility.PUBLIC
        ):
            return await self._latest_published_release(product)

        raise EntityNotFoundError(product.oid)

    async def _latest_published_release(
        self,
        product: Product,
    ) -> NoteReleaseID:
        if product.status is not ProductStatus.PUBLISHED:
            # A collaborator on a still-DRAFT note has no released
            # content to search — surface as 404, same as the scheme.
            raise EntityNotFoundError(product.oid)
        latest = await self._release_gateway.latest_for_product(
            product.oid,
        )
        if latest is None:
            raise EntityNotFoundError(product.oid)
        return latest.oid

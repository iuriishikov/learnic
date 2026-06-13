from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.enrollment import (
    EnrollmentGateway,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseReader,
    ReleaseLessonContentView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.enrollment.details import NoteEnrollmentDetails
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.enums import ProductStatus, ProductVisibility
from learnic.entities.product.models import Product
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetReleaseLessonQuery:
    actor_id: UserID | None
    """``None`` for an anonymous caller (no access cookie)."""
    lesson_id: NoteLessonID
    """Release-side lesson id (as listed by the scheme endpoint)."""


@final
class GetReleaseLessonQueryHandler:
    """Return one release lesson's blocks for the current viewer.

    The per-lesson companion of ``GetNoteSchemeQueryHandler``: the
    scheme hands the SPA the lesson ids, this query loads one
    lesson's block payloads on demand. Access is decided per
    *viewer class*, first match wins:

        1. Actively-enrolled student whose **pinned** release
           contains the lesson — strict pinning still holds; a
           lesson from another release falls through to rule 3.
        2. Product author / collaborator with ``READ_PRODUCT`` —
           any release, any product status (checked non-raising
           via :meth:`Authorizer.effective_permissions` so denial
           falls through instead of leaking a 403).
        3. Anyone, including anonymous — the product is
           ``PUBLISHED`` **and** openly distributed
           (``ProductVisibility.PUBLIC``).
        4. Everything else → ``EntityNotFoundError``. The 404 is
           uniform across all "no access" cases so the response
           shape does not leak why the caller was rejected.

    Blocks are returned as views; the route projects them through
    the public schema set, stripping interactive answers.
    """

    def __init__(
        self,
        product_gateway: ProductGateway,
        enrollment_gateway: EnrollmentGateway,
        authorizer: Authorizer,
        release_reader: NoteReleaseReader,
    ) -> None:
        self._product_gateway: Final = product_gateway
        self._enrollment_gateway: Final = enrollment_gateway
        self._authorizer: Final = authorizer
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: GetReleaseLessonQuery,
    ) -> ReleaseLessonContentView:
        view = await self._release_reader.get_lesson(data.lesson_id)
        if view is None:
            raise EntityNotFoundError(data.lesson_id)

        product = await self._product_gateway.with_id(view.product_id)
        if product is None or not product.supports(
            ProductCapability.HAS_NOTE_CONTENT,
        ):
            # Same hiding policy as the check/reveal flow: non-note
            # products are surfaced as 404, not 409.
            raise EntityNotFoundError(data.lesson_id)

        if not await self._is_allowed(product, view, data.actor_id):
            raise EntityNotFoundError(data.lesson_id)
        return view

    async def _is_allowed(
        self,
        product: Product,
        view: ReleaseLessonContentView,
        actor_id: UserID | None,
    ) -> bool:
        if actor_id is not None:
            # Most common viewer first: the enrolled student
            # reading their pinned release.
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
                if enrollment.details.release_id == view.release_id:
                    return True

            # Author / collaborator: non-raising permission probe —
            # ``require`` would 403 and leak that the lesson exists.
            permissions = await self._authorizer.effective_permissions(
                actor_id,
                AuthzTarget.for_product(product.oid),
            )
            if (
                permissions is not None
                and Permission.READ_PRODUCT in permissions
            ):
                return True

        # Open distribution: any viewer, any release of the product.
        return (
            product.status is ProductStatus.PUBLISHED
            and product.visibility is ProductVisibility.PUBLIC
        )

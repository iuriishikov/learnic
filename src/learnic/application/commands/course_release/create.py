from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    ContentEventKind,
    publish_content_event,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_release import (
    CourseReleaseGateway,
    CourseReleaseSnapshotter,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    publish_product_event,
)
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.course_release.value_objects import ReleaseNotes
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CreateCourseReleaseCommand:
    actor_id: UserID
    product_id: ProductID
    kind: CourseReleaseKind
    notes: str | None = None


@final
class CreateCourseReleaseCommandHandler:
    """Snapshot the course's draft into a new immutable release.

    Steps inside one transaction:
      1. Verify ownership and that the product is a course.
      2. Look up the latest release; bump version per ``kind``.
         No prior release means baseline ``v0.0.0`` → ``patch``
         yields ``v0.0.1``, ``minor`` → ``v0.1.0``, ``major`` →
         ``v1.0.0``.
      3. Persist the new ``CourseRelease`` row.
      4. Run :class:`CourseReleaseSnapshotter` to copy modules,
         lessons and blocks (+ child rows) into the snapshot
         mirror tables, pinning every row to the new release id.
      5. If this is the first release, flip the product status to
         ``PUBLISHED`` (auto-publish on first release).
      6. Commit.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        release_gateway: CourseReleaseGateway,
        snapshotter: CourseReleaseSnapshotter,
        event_bus: ContentEventBus,
        product_event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._release_gateway: Final = release_gateway
        self._snapshotter: Final = snapshotter
        self._event_bus: Final = event_bus
        self._product_event_bus: Final = product_event_bus

    async def run(
        self,
        data: CreateCourseReleaseCommand,
    ) -> CourseRelease:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_RELEASES,
        )
        product.require_supports(ProductCapability.HAS_COURSE_RELEASES)

        previous = await self._release_gateway.latest_for_product(
            data.product_id,
        )
        ordinal = (previous.ordinal + 1) if previous is not None else 1
        notes = ReleaseNotes(data.notes) if data.notes is not None else None

        release = CourseRelease.create(
            product_id=data.product_id,
            ordinal=ordinal,
            previous_version=(previous.version if previous is not None else None),
            kind=data.kind,
            released_by=data.actor_id,
            notes=notes,
        )
        self._entity_saver.add_one(release)
        # Make the release row visible to the snapshotter's INSERTs
        # which FK to course_releases.oid.
        await self._transaction.flush()

        await self._snapshotter.snapshot(release)

        auto_published = False
        if previous is None and product.status is ProductStatus.DRAFT:
            product.publish()
            auto_published = True

        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            kind=ContentEventKind.RELEASE_CREATED,
            product_id=data.product_id,
            actor_id=data.actor_id,
            payload={
                "release_id": str(release.oid),
                "ordinal": release.ordinal,
                "version": [
                    release.version.major,
                    release.version.minor,
                    release.version.patch,
                ],
                "kind": release.kind.value,
            },
        )
        if auto_published:
            assert product.published_at is not None
            await publish_product_event(
                self._product_event_bus,
                kind=ProductEventKind.PUBLISHED,
                product_id=product.oid,
                actor_id=data.actor_id,
                payload={
                    "status": product.status.value,
                    "published_at": product.published_at.isoformat(),
                },
            )
        return release

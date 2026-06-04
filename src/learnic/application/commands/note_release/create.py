from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    ReleaseCreatedPayload,
    publish_content_event,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_release import (
    NoteReleaseGateway,
    NoteReleaseSnapshotter,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.product_events import (
    ProductEventBus,
    PublishedPayload,
    publish_product_event,
)
from learnic.entities.common.limits import NOTE_RELEASE_LIMIT
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.models import NoteRelease
from learnic.entities.note_release.value_objects import ReleaseNotes
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CreateNoteReleaseCommand:
    actor_id: UserID
    product_id: ProductID
    kind: NoteReleaseKind
    notes: str | None = None


@final
class CreateNoteReleaseCommandHandler:
    """Snapshot the note's draft into a new immutable release.

    Steps inside one transaction:
      1. Verify ownership and that the product is a note.
      2. Look up the latest release; bump version per ``kind``.
         No prior release means baseline ``v0.0.0`` → ``patch``
         yields ``v0.0.1``, ``minor`` → ``v0.1.0``, ``major`` →
         ``v1.0.0``.
      3. Persist the new ``NoteRelease`` row.
      4. Run :class:`NoteReleaseSnapshotter` to copy modules,
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
        release_gateway: NoteReleaseGateway,
        snapshotter: NoteReleaseSnapshotter,
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
        data: CreateNoteReleaseCommand,
    ) -> NoteRelease:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_RELEASES,
        )
        product.require_supports(ProductCapability.HAS_NOTE_RELEASES)
        NOTE_RELEASE_LIMIT.ensure(
            await self._release_gateway.count_for_product(data.product_id),
        )

        previous = await self._release_gateway.latest_for_product(
            data.product_id,
        )
        ordinal = (previous.ordinal + 1) if previous is not None else 1
        notes = ReleaseNotes(data.notes) if data.notes is not None else None

        release = NoteRelease.create(
            product_id=data.product_id,
            ordinal=ordinal,
            previous_version=(previous.version if previous is not None else None),
            kind=data.kind,
            released_by=data.actor_id,
            notes=notes,
        )
        self._entity_saver.add_one(release)
        # Make the release row visible to the snapshotter's INSERTs
        # which FK to note_releases.oid.
        await self._transaction.flush()

        await self._snapshotter.snapshot(release)

        auto_published = False
        if previous is None and product.status is ProductStatus.DRAFT:
            product.publish()
            auto_published = True

        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=ReleaseCreatedPayload.from_entity(release),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        if auto_published:
            assert product.published_at is not None
            await publish_product_event(
                self._product_event_bus,
                payload=PublishedPayload(
                    status=product.status.value,
                    published_at=product.published_at.isoformat(),
                ),
                product_id=product.oid,
                actor_id=data.actor_id,
            )
        return release

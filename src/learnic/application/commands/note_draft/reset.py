from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.collaboration import (
    ContentEventBus,
    DraftResetPayload,
    publish_content_event,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.file import FilesReader
from learnic.application.common.persistence.note_draft import (
    NoteDraftResetter,
)
from learnic.application.common.persistence.note_release import (
    NoteReleaseGateway,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
)
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ResetNoteDraftCommand:
    actor_id: UserID
    product_id: ProductID
    release_id: NoteReleaseID


@final
class ResetNoteDraftCommandHandler:
    """Discard the current draft and rehydrate it from a release snapshot.

    Behavior:
        1. Authorize the actor: requires ``MANAGE_RELEASES`` on the
           product (the owner has it implicitly; a collaborator with a
           role granting it is allowed too — this is NOT author-only).
        2. Verify ``release_id`` exists and belongs to the same product
           — guards against pointing at another product's release.
        3. Wipe current draft (modules cascade lessons / blocks /
           child rows via FK) and soft-delete the draft-only files
           those blocks referenced — the cascade drops the blocks but
           NOT the parent ``files`` rows, so without this sweep the
           rows linger live (quota-visible) and the S3 blobs orphan
           forever. Release-pinned files are spared by
           ``soft_delete_previous``; the product cover is excluded.
        4. Insert fresh draft rows from the release snapshot tables,
           generating new UUIDs for every restored row so draft ids
           stay disjoint from snapshot ids.
        5. Commit and publish a ``DRAFT_RESET`` content event so
           connected authors refetch the tree.

    Effect on existing release(s): none. Snapshots are immutable
    and untouched. Students stay on whatever release_id their
    enrollment pinned them to.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        release_gateway: NoteReleaseGateway,
        resetter: NoteDraftResetter,
        files_reader: FilesReader,
        file_uploads: FileUploadService,
        event_bus: ContentEventBus,
        quota_publisher: StorageQuotaUsagePublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._release_gateway: Final = release_gateway
        self._resetter: Final = resetter
        self._files_reader: Final = files_reader
        self._file_uploads: Final = file_uploads
        self._event_bus: Final = event_bus
        self._quota_publisher: Final = quota_publisher

    async def run(self, data: ResetNoteDraftCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_RELEASES,
        )
        product.require_supports(ProductCapability.HAS_NOTE_CONTENT)

        release = await self._release_gateway.with_id(data.release_id)
        if release is None or release.product_id != data.product_id:
            raise EntityNotFoundError(data.release_id)

        # Snapshot the draft's content files BEFORE the wipe — afterwards
        # the cascade has dropped the block rows and the union-walk would
        # return nothing. Exclude the product cover: reset rebuilds only
        # the content tree, the cover is untouched and must not be swept.
        # Files the rehydrated draft re-references (the snapshot's) are
        # spared inside soft_delete_previous by its release guard, so only
        # post-release draft-only uploads are actually freed.
        file_ids = [
            file_id
            for file_id in await self._files_reader.file_ids_for_product(
                data.product_id,
            )
            if file_id != product.cover_file_id
        ]
        await self._resetter.reset(release)
        freed = False
        for file_id in file_ids:
            if await self._file_uploads.soft_delete_previous(file_id):
                freed = True
        await self._transaction.commit()
        await publish_content_event(
            self._event_bus,
            payload=DraftResetPayload.from_entity(release),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        if freed:
            await self._quota_publisher.usage_changed(product.author_id)

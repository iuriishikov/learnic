"""Per-note storage-panel query.

One round-trip for the editor's storage card: how many bytes THIS
note's files occupy, plus the author's pool numbers (cap / used /
remaining). Anchored on the note author — a collaborator opening
the editor sees the same figures the author would, since they
share one quota pool. Supersedes nothing: the slimmer
``GetNoteStorageRemainingQuery`` stays for callers that only need
headroom.
"""

from dataclasses import dataclass
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.billing import FileUsageReader
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.billing.ids import PlanCode
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetNoteStorageQuery:
    actor_id: UserID
    note_id: ProductID


@dataclass(slots=True, frozen=True)
class NoteStorageView:
    """Read-side projection for the per-note storage endpoint.

    ``note_storage_bytes_used`` counts only files referenced from
    THIS note's blocks (deduplicated, soft-deleted excluded, cover
    not counted — covers sit outside the quota aggregate). The
    remaining three numbers describe the author's whole pool, so
    ``note_storage_bytes_used <= storage_bytes_used`` always holds.
    ``storage_bytes_remaining`` is clamped to 0.
    """

    plan_code: PlanCode
    note_storage_bytes_used: int
    storage_bytes_max: int
    storage_bytes_used: int
    storage_bytes_remaining: int


@final
class GetNoteStorageQueryHandler:
    """Resolve the note's author and report note + pool usage.

    The actor must hold ``EDIT_LESSONS`` on the note — same gate as
    the upload commands and the storage-remaining read. Read-only:
    no advisory lock, the values are informational and re-validated
    by :meth:`EntitlementService.ensure_can_upload` at upload time.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        entitlement: EntitlementService,
        file_usage: FileUsageReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._entitlement: Final = entitlement
        self._file_usage: Final = file_usage

    async def run(self, data: GetNoteStorageQuery) -> NoteStorageView:
        product = await self._product_gateway.with_id(data.note_id)
        if product is None:
            raise EntityNotFoundError(data.note_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.note_id),
            Permission.EDIT_LESSONS,
        )
        snapshot = await self._entitlement.snapshot_for(product.author_id)
        note_used = await self._file_usage.bytes_used_by_product(
            data.note_id,
        )
        return NoteStorageView(
            plan_code=snapshot.plan.code,
            note_storage_bytes_used=note_used,
            storage_bytes_max=snapshot.plan.limits.storage_bytes_max,
            storage_bytes_used=snapshot.used_bytes,
            storage_bytes_remaining=snapshot.remaining_bytes,
        )

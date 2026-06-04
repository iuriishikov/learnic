from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.user import UserView
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.ids import (
    CollaborationGrantID,
    ProductCollaborationID,
)
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import ScopeType
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CollaborationGrantView:
    oid: CollaborationGrantID
    role_id: RoleID
    role_name: str
    scope_type: ScopeType
    scope_id: UUID | None


@dataclass(slots=True, frozen=True)
class ProductCollaborationView:
    oid: ProductCollaborationID
    product_id: ProductID
    collaborator: UserView | None
    invited_email: str | None
    status: CollaborationStatus
    invited_by: UserID
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    grants: tuple[CollaborationGrantView, ...]


class ProductCollaborationGateway(Protocol):
    """Write-side lookups for :class:`ProductCollaboration`.

    ``with_id`` and the ``*_for_*`` variants always return a
    fully-hydrated aggregate including ``grants`` (loaded by the
    adapter through a follow-up query, mirroring the
    ``Product.webinar_details`` pattern).
    """

    async def with_id(
        self,
        oid: ProductCollaborationID,
    ) -> ProductCollaboration | None: ...

    async def with_id_for_update(
        self,
        oid: ProductCollaborationID,
    ) -> ProductCollaboration | None:
        """Like :meth:`with_id` but locks the row ``FOR UPDATE``.

        Used by state-transition handlers (accept) so the
        ``PENDING_INVITE`` guard and the status flip are serialized
        across replicas: a second concurrent accept blocks here,
        then re-reads the now-``ACTIVE`` row and is rejected by
        ``require_op`` (``OperationNotAllowedInStatusError``) instead
        of double-firing the accept fan-out. The lock is held until
        the handler commits.
        """
        ...

    async def active_for_product_and_user(
        self,
        product_id: ProductID,
        collaborator_id: UserID,
    ) -> ProductCollaboration | None:
        """Return the active or pending collaboration for ``(product, user)``.

        Excludes ``REVOKED`` rows. Used by ``Authorizer`` to load
        the caller's effective grants and by invite handlers to
        guard against duplicate invites.
        """
        ...

    async def pending_for_product_and_email(
        self,
        product_id: ProductID,
        invited_email: str,
    ) -> ProductCollaboration | None:
        """Return the pending email-invite for ``(product, email)``.

        Used to prevent issuing two pending email invites to the
        same address for the same product.
        """
        ...

    async def count_active_or_pending_for_product(
        self,
        product_id: ProductID,
    ) -> int:
        """Count live (active + pending) collaborations on a product.

        Used by the invite handlers to enforce
        :data:`PRODUCT_COLLABORATION_LIMIT`. Counts only
        ``PENDING_INVITE`` and ``ACTIVE`` rows — ``DECLINED`` /
        ``REVOKED`` are terminal audit rows that no longer occupy a
        collaborator slot, so they must not count toward the cap
        (same closed-set discipline as :meth:`RoleGateway.is_in_use`).
        """
        ...

    async def count_email_invites_by_actor_since(
        self,
        actor_id: UserID,
        since: datetime,
    ) -> int:
        """Count email-based invites issued by ``actor_id`` since ``since``.

        Used by ``InviteCollaboratorByEmailCommandHandler`` to enforce
        a per-actor daily cap so a malicious / compromised account
        cannot drain the upstream email provider's quota with a flood
        of invitations to attacker-controlled addresses. Counts every
        row created in the window across all products — accepted and
        revoked rows included, because the email (and the upstream
        token) was already spent regardless of later state.
        """
        ...

    async def delete_expired_pending_invites(
        self,
        expires_before: datetime,
    ) -> int:
        """Delete ``PENDING_INVITE`` rows past their ``invite_expires_at``.

        Used by ``PurgeExpiredInvitesCommandHandler`` as a periodic
        sweep: acceptance only validates the TTL at call time and
        never cleans up, so expired pending rows accumulate and
        keep the partial unique index on
        ``(product_id, invited_email)`` for pending invites
        occupied. The strict ``invite_expires_at < expires_before``
        bound matches the validation logic on
        :meth:`ProductCollaboration.accept` exactly — rows that
        would still be acceptable are never touched.

        Grant rows are removed transitively through the FK
        ``collaboration_grants.collaboration_id`` (``ON DELETE
        CASCADE``); no separate cleanup is needed. Returns the
        number of deleted parent rows so the caller can log the
        sweep size.
        """
        ...


class ProductCollaborationSaver(Protocol):
    """Write-side persistence for :class:`ProductCollaboration` grants.

    Mirrors :class:`RoleSaver` — :attr:`ProductCollaboration.grants`
    lives in :data:`collaboration_grants_table`, not on the parent
    row, so ``EntitySaver.add_one`` is not enough on its own. Handlers
    call :meth:`save` for fresh invitations and :meth:`replace_grants`
    when ``UpdateCollaborationGrantsCommand`` rewrites the grant set.
    """

    async def save(self, collaboration: ProductCollaboration) -> None:
        """Persist the parent collaboration plus its grant rows.

        The implementation flushes the parent first so the FK from
        ``collaboration_grants.collaboration_id`` is satisfied
        before grant rows are inserted.
        """
        ...

    async def replace_grants(
        self,
        collaboration: ProductCollaboration,
    ) -> None:
        """Atomically replace the persisted grant set."""
        ...


class ProductCollaborationReader(Protocol):
    """Read-side queries returning :class:`ProductCollaborationView`."""

    async def with_id(
        self,
        oid: ProductCollaborationID,
    ) -> ProductCollaborationView | None: ...

    async def for_product(
        self,
        product_id: ProductID,
        pagination: Pagination,
    ) -> list[ProductCollaborationView]: ...

    async def for_user(
        self,
        collaborator_id: UserID,
        pagination: Pagination,
    ) -> list[ProductCollaborationView]: ...

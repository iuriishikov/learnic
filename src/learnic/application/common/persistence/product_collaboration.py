from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from learnic.application.common.pagination import Pagination
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
class CollaboratorView:
    """Read-side projection embedded in :class:`ProductCollaborationView`."""

    oid: UserID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None


@dataclass(slots=True, frozen=True)
class ProductCollaborationView:
    oid: ProductCollaborationID
    product_id: ProductID
    collaborator: CollaboratorView | None
    invited_email: str | None
    status: CollaborationStatus
    invited_by: UserID
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
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

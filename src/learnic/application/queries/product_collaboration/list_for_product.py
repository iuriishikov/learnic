from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.formatting import mask_email
from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product_collaboration import (
    CollaborationGrantView,
    ProductCollaborationReader,
    ProductCollaborationView,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.user.get import (
    UserOutput,
    resolve_user_output,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ProductCollaborationOutput:
    """Collaboration projection with the collaborator resolved.

    Mirrors :class:`ProductCollaborationView` but ``collaborator``
    carries the unified user projection (avatar/cover presigned URLs
    signed) so the HTTP layer maps it straight to ``UserSchema``.
    ``invited_email`` is already masked. ``grants`` pass through
    unchanged.
    """

    oid: ProductCollaborationID
    product_id: ProductID
    collaborator: UserOutput | None
    invited_email: str | None
    status: CollaborationStatus
    invited_by: UserID
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None
    grants: tuple[CollaborationGrantView, ...]


async def resolve_collaboration_output(
    view: ProductCollaborationView,
    file_storage: FileStorage,
) -> ProductCollaborationOutput:
    """Inflate a view into a :class:`ProductCollaborationOutput`.

    Single call site for collaboration embedded-user resolution;
    reused by the for-product and my-collaborations query handlers.
    """
    return ProductCollaborationOutput(
        oid=view.oid,
        product_id=view.product_id,
        collaborator=(
            await resolve_user_output(view.collaborator, file_storage)
            if view.collaborator is not None
            else None
        ),
        invited_email=(
            mask_email(view.invited_email)
            if view.invited_email is not None
            else None
        ),
        status=view.status,
        invited_by=view.invited_by,
        invite_expires_at=view.invite_expires_at,
        created_at=view.created_at,
        accepted_at=view.accepted_at,
        declined_at=view.declined_at,
        revoked_at=view.revoked_at,
        grants=view.grants,
    )


@dataclass(slots=True, frozen=True)
class ListProductCollaboratorsQuery:
    actor_id: UserID
    product_id: ProductID
    pagination: Pagination


@final
class ListProductCollaboratorsQueryHandler:
    """Lists collaborators (and pending invites) for a product.

    Caller needs ``READ_PRODUCT`` — any collaborator can see who
    else is on the team, but only those with
    ``MANAGE_COLLABORATORS`` may invite or revoke (enforced on the
    write commands). The team list is part of the product's
    overview, not a privileged view.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        reader: ProductCollaborationReader,
        file_storage: FileStorage,
    ) -> None:
        self._authorizer: Final = authorizer
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(
        self,
        data: ListProductCollaboratorsQuery,
    ) -> list[ProductCollaborationOutput]:
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.READ_PRODUCT,
        )
        views = await self._reader.for_product(
            data.product_id,
            data.pagination,
        )
        return [
            await resolve_collaboration_output(view, self._file_storage)
            for view in views
        ]

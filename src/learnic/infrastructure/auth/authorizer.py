from typing import Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.auth.resource_lineage import (
    ResourceLineageReader,
)
from learnic.application.common.errors import (
    InsufficientPermissionsError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import (
    Permission,
    ScopeType,
    expand_implied,
)
from learnic.entities.role.value_objects import PermissionSet
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.product_collaboration import (
    collaboration_grants_table,
    product_collaborations_table,
)
from learnic.infrastructure.persistence.models.role import (
    role_permissions_table,
)


class AuthorizerService(Authorizer):
    """SQL-backed :class:`Authorizer` implementation.

    Loads the product author once, falls back to the caller's
    active collaboration when the actor is not the owner, and
    resolves the effective permission set across all covering
    grants. Permission implications are expanded centrally via
    :func:`expand_implied` so the resolution rule lives in one
    place.
    """

    def __init__(
        self,
        session: AsyncSession,
        collaborations: ProductCollaborationGateway,
        lineage: ResourceLineageReader,
    ) -> None:
        self._session: Final = session
        self._collaborations: Final = collaborations
        self._lineage: Final = lineage

    @override
    async def require(
        self,
        actor: UserID,
        target: AuthzTarget,
        permission: Permission,
    ) -> None:
        permissions = await self.effective_permissions(actor, target)
        if permissions is None or permission not in permissions:
            raise InsufficientPermissionsError(
                user_id=actor,
                product_id=target.product_id,
                permission=permission.value,
                target_id=target.target_id,
            )

    @override
    async def require_owner(
        self,
        actor: UserID,
        product_id: ProductID,
    ) -> None:
        target = AuthzTarget.for_product(product_id)
        if not await self._is_product_owner(actor, target):
            raise NotResourceOwnerError(
                resource_id=product_id,
                user_id=actor,
            )

    @override
    async def effective_permissions(
        self,
        actor: UserID,
        target: AuthzTarget,
    ) -> PermissionSet | None:
        if await self._is_product_owner(actor, target):
            return PermissionSet(frozenset(Permission))

        collab = await self._collaborations.active_for_product_and_user(
            target.product_id,
            actor,
        )
        if collab is None or collab.status is not CollaborationStatus.ACTIVE:
            return None

        resolved = await self._resolve_target(target)
        if resolved is None:
            return None

        covering_role_ids = self._covering_role_ids(
            collab.grants,
            resolved,
        )
        if not covering_role_ids:
            return None
        permissions = await self._load_permissions(covering_role_ids)
        if not permissions:
            return None
        return PermissionSet(expand_implied(permissions))

    @override
    async def manage_collaborators_for_products(
        self,
        actor: UserID,
        product_ids: set[ProductID],
    ) -> dict[ProductID, bool]:
        if not product_ids:
            return {}
        ids = list(product_ids)
        # 1. Owner short-circuit, batched into one query.
        owned_rows = (
            await self._session.execute(
                sa.select(products_table.c.oid).where(
                    products_table.c.oid.in_(ids),
                    products_table.c.author_id == actor,
                ),
            )
        ).scalars().all()
        owned = {ProductID(oid) for oid in owned_rows}

        # 2. Collaborator path: an ACTIVE collaboration with a
        #    PRODUCT-scope grant whose role carries MANAGE_COLLABORATORS.
        #    That permission is a leaf (nothing in PERMISSION_IMPLIES
        #    yields it) and product-scoped, so this direct join is a
        #    complete equivalent of effective_permissions(...) for it —
        #    no implication expansion can add it.
        remaining = [pid for pid in ids if pid not in owned]
        managed: set[ProductID] = set()
        if remaining:
            rows = (
                await self._session.execute(
                    sa.select(product_collaborations_table.c.product_id)
                    .select_from(
                        product_collaborations_table.join(
                            collaboration_grants_table,
                            collaboration_grants_table.c.collaboration_id
                            == product_collaborations_table.c.oid,
                        ).join(
                            role_permissions_table,
                            role_permissions_table.c.role_id
                            == collaboration_grants_table.c.role_id,
                        ),
                    )
                    .where(
                        product_collaborations_table.c.product_id.in_(
                            remaining,
                        ),
                        product_collaborations_table.c.collaborator_id
                        == actor,
                        product_collaborations_table.c.status
                        == CollaborationStatus.ACTIVE.value,
                        collaboration_grants_table.c.scope_type
                        == ScopeType.PRODUCT.value,
                        role_permissions_table.c.permission
                        == Permission.MANAGE_COLLABORATORS.value,
                    )
                    .distinct(),
                )
            ).scalars().all()
            managed = {ProductID(pid) for pid in rows}

        return {pid: pid in owned or pid in managed for pid in product_ids}

    async def _is_product_owner(
        self,
        actor: UserID,
        target: AuthzTarget,
    ) -> bool:
        stmt = sa.select(products_table.c.author_id).where(
            products_table.c.oid == target.product_id,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        return row is not None and row.author_id == actor

    async def _resolve_target(
        self,
        target: AuthzTarget,
    ) -> "_ResolvedTarget | None":
        if target.target_type is ScopeType.PRODUCT:
            return _ResolvedTarget(
                product_id=target.product_id,
                target_type=ScopeType.PRODUCT,
                target_id=None,
                module_id=None,
            )
        if target.target_type is ScopeType.MODULE:
            if target.target_id is None:
                return None
            module_id = target.module_id or target.target_id
            return _ResolvedTarget(
                product_id=target.product_id,
                target_type=ScopeType.MODULE,
                target_id=target.target_id,
                module_id=module_id,
            )
        # LESSON
        if target.target_id is None:
            return None
        if target.module_id is not None:
            return _ResolvedTarget(
                product_id=target.product_id,
                target_type=ScopeType.LESSON,
                target_id=target.target_id,
                module_id=target.module_id,
            )
        lineage = await self._lineage.lineage_for_lesson(target.target_id)
        if lineage is None:
            return None
        return _ResolvedTarget(
            product_id=lineage.product_id,
            target_type=ScopeType.LESSON,
            target_id=target.target_id,
            module_id=lineage.module_id,
        )

    @staticmethod
    def _covering_role_ids(
        grants: list[CollaborationGrant],
        target: "_ResolvedTarget",
    ) -> list[RoleID]:
        return [
            grant.role_id
            for grant in grants
            if grant.covers(
                target.target_type,
                target.target_id,
                target_module_id=target.module_id,
            )
        ]

    async def _load_permissions(
        self,
        role_ids: list[RoleID],
    ) -> frozenset[Permission]:
        if not role_ids:
            return frozenset()
        stmt = sa.select(role_permissions_table.c.permission).where(
            role_permissions_table.c.role_id.in_(role_ids),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return frozenset(Permission(p) for p in rows)


class _ResolvedTarget:
    __slots__ = ("product_id", "target_type", "target_id", "module_id")

    def __init__(
        self,
        *,
        product_id: object,
        target_type: ScopeType,
        target_id: UUID | None,
        module_id: UUID | None,
    ) -> None:
        self.product_id = product_id
        self.target_type = target_type
        self.target_id = target_id
        self.module_id = module_id

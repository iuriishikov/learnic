from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product_collaboration import (
    CollaborationGrantView,
    ProductCollaborationGateway,
    ProductCollaborationReader,
    ProductCollaborationSaver,
    ProductCollaborationView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.grant import CollaborationGrant
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
from learnic.infrastructure.persistence.models.product_collaboration import (
    collaboration_grants_table,
    product_collaborations_table,
)
from learnic.infrastructure.persistence.models.role import roles_table
from learnic.infrastructure.persistence.models.user import users_table


class ProductCollaborationMapperAlchemy(ProductCollaborationGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: ProductCollaborationID,
    ) -> ProductCollaboration | None:
        stmt = sa.select(ProductCollaboration).where(
            product_collaborations_table.c.oid == oid,
        )
        collab = (await self._session.execute(stmt)).scalar_one_or_none()
        if collab is None:
            return None
        collab.grants = await self._load_grants(collab.oid)
        return collab

    @override
    async def active_for_product_and_user(
        self,
        product_id: ProductID,
        collaborator_id: UserID,
    ) -> ProductCollaboration | None:
        stmt = sa.select(ProductCollaboration).where(
            product_collaborations_table.c.product_id == product_id,
            product_collaborations_table.c.collaborator_id == collaborator_id,
            sa.or_(
                product_collaborations_table.c.status
                == CollaborationStatus.ACTIVE.value,
                product_collaborations_table.c.status
                == CollaborationStatus.PENDING_INVITE.value,
            ),
        )
        collab = (await self._session.execute(stmt)).scalar_one_or_none()
        if collab is None:
            return None
        collab.grants = await self._load_grants(collab.oid)
        return collab

    @override
    async def pending_for_product_and_email(
        self,
        product_id: ProductID,
        invited_email: str,
    ) -> ProductCollaboration | None:
        stmt = sa.select(ProductCollaboration).where(
            product_collaborations_table.c.product_id == product_id,
            product_collaborations_table.c.invited_email == invited_email,
            product_collaborations_table.c.status
            == CollaborationStatus.PENDING_INVITE.value,
        )
        collab = (await self._session.execute(stmt)).scalar_one_or_none()
        if collab is None:
            return None
        collab.grants = await self._load_grants(collab.oid)
        return collab

    @override
    async def count_email_invites_by_actor_since(
        self,
        actor_id: UserID,
        since: datetime,
    ) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(
                product_collaborations_table,
            )
            .where(
                product_collaborations_table.c.invited_by == actor_id,
                product_collaborations_table.c.invited_email.is_not(None),
                product_collaborations_table.c.created_at >= since,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    @override
    async def delete_expired_pending_invites(
        self,
        expires_before: datetime,
    ) -> int:
        # ``invite_expires_at`` is non-null for every PENDING_INVITE
        # row by construction (model invariant), but the explicit
        # ``is_not(None)`` keeps the predicate well-defined even if
        # a future migration ever loosens that, and lets Postgres
        # use the partial index without pulling NULL rows.
        # Grants cascade through the FK ``ON DELETE CASCADE`` on
        # ``collaboration_grants.collaboration_id``.
        stmt = sa.delete(product_collaborations_table).where(
            product_collaborations_table.c.status
            == CollaborationStatus.PENDING_INVITE.value,
            product_collaborations_table.c.invite_expires_at.is_not(None),
            product_collaborations_table.c.invite_expires_at < expires_before,
        )
        result = await self._session.execute(stmt)
        # ``CursorResult.rowcount`` at runtime; the ``getattr`` matches
        # ``token_denylist`` / ``notification`` adapters and dodges the
        # ``Result[Any]`` static type that lacks the attribute.
        rowcount: int | None = getattr(result, "rowcount", None)
        return rowcount or 0

    async def _load_grants(
        self,
        collaboration_id: ProductCollaborationID,
    ) -> list[CollaborationGrant]:
        stmt = sa.select(CollaborationGrant).where(
            collaboration_grants_table.c.collaboration_id == collaboration_id,
        )
        return list(
            (await self._session.execute(stmt)).scalars().all(),
        )


class ProductCollaborationSaverAlchemy(ProductCollaborationSaver):
    """SQL-backed :class:`ProductCollaborationSaver`.

    The parent collaboration row goes through the SA Unit of Work,
    grants are inserted via SA Core into
    :data:`collaboration_grants_table` directly. ``flush()``
    materialises the parent PK so the grants' FK is satisfied.

    Grants are not loaded back as ORM entities here — the gateway
    re-loads them via :meth:`_load_grants` when needed. This keeps
    grant lifecycle entirely under the saver and avoids accidental
    dirty-flag interactions with the SA UnitOfWork.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def save(
        self,
        collaboration: ProductCollaboration,
    ) -> None:
        self._session.add(collaboration)
        await self._session.flush()
        await self._insert_grants(collaboration.oid, collaboration.grants)

    @override
    async def replace_grants(
        self,
        collaboration: ProductCollaboration,
    ) -> None:
        await self._session.execute(
            sa.delete(collaboration_grants_table).where(
                collaboration_grants_table.c.collaboration_id == collaboration.oid,
            ),
        )
        await self._insert_grants(collaboration.oid, collaboration.grants)

    async def _insert_grants(
        self,
        collaboration_id: ProductCollaborationID,
        grants: list[CollaborationGrant],
    ) -> None:
        if not grants:
            return
        await self._session.execute(
            sa.insert(collaboration_grants_table),
            [
                {
                    "oid": grant.oid,
                    "collaboration_id": collaboration_id,
                    "role_id": grant.role_id,
                    "scope_type": grant.scope_type.value,
                    "scope_id": grant.scope_id,
                }
                for grant in grants
            ],
        )


def _row_to_collaborator(row: sa.Row[Any]) -> UserRefView | None:
    if row.collaborator_oid is None:
        return None
    return UserRefView(
        oid=UserID(row.collaborator_oid),
        email=row.collaborator_email,
        first_name=row.collaborator_first_name,
        last_name=row.collaborator_last_name,
        patronymic=row.collaborator_patronymic,
    )


class ProductCollaborationReaderAlchemy(ProductCollaborationReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: ProductCollaborationID,
    ) -> ProductCollaborationView | None:
        stmt = self._select_with_user().where(
            product_collaborations_table.c.oid == oid,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        grants = await self._load_grants(
            [ProductCollaborationID(row.oid)],
        )
        return self._row_to_view(row, grants[ProductCollaborationID(row.oid)])

    @override
    async def for_product(
        self,
        product_id: ProductID,
        pagination: Pagination,
    ) -> list[ProductCollaborationView]:
        stmt = (
            self._select_with_user()
            .where(product_collaborations_table.c.product_id == product_id)
            .order_by(product_collaborations_table.c.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return await self._rows_to_views(rows)

    @override
    async def for_user(
        self,
        collaborator_id: UserID,
        pagination: Pagination,
    ) -> list[ProductCollaborationView]:
        stmt = (
            self._select_with_user()
            .where(
                product_collaborations_table.c.collaborator_id == collaborator_id,
            )
            .order_by(product_collaborations_table.c.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return await self._rows_to_views(rows)

    def _select_with_user(self) -> sa.Select[Any]:
        return sa.select(
            product_collaborations_table.c.oid,
            product_collaborations_table.c.product_id,
            product_collaborations_table.c.collaborator_id,
            product_collaborations_table.c.invited_email,
            product_collaborations_table.c.status,
            product_collaborations_table.c.invited_by,
            product_collaborations_table.c.invite_expires_at,
            product_collaborations_table.c.created_at,
            product_collaborations_table.c.accepted_at,
            product_collaborations_table.c.declined_at,
            product_collaborations_table.c.revoked_at,
            users_table.c.oid.label("collaborator_oid"),
            users_table.c.email.label("collaborator_email"),
            users_table.c.first_name.label("collaborator_first_name"),
            users_table.c.last_name.label("collaborator_last_name"),
            users_table.c.patronymic.label("collaborator_patronymic"),
        ).select_from(
            product_collaborations_table.outerjoin(
                users_table,
                product_collaborations_table.c.collaborator_id == users_table.c.oid,
            ),
        )

    def _row_to_view(
        self,
        row: sa.Row[Any],
        grants: tuple[CollaborationGrantView, ...],
    ) -> ProductCollaborationView:
        return ProductCollaborationView(
            oid=ProductCollaborationID(row.oid),
            product_id=ProductID(row.product_id),
            collaborator=_row_to_collaborator(row),
            invited_email=row.invited_email,
            status=row.status,
            invited_by=UserID(row.invited_by),
            invite_expires_at=row.invite_expires_at,
            created_at=row.created_at,
            accepted_at=row.accepted_at,
            declined_at=row.declined_at,
            revoked_at=row.revoked_at,
            grants=grants,
        )

    async def _rows_to_views(
        self,
        rows: Sequence[sa.Row[Any]],
    ) -> list[ProductCollaborationView]:
        if not rows:
            return []
        ids = [ProductCollaborationID(row.oid) for row in rows]
        grants = await self._load_grants(ids)
        return [
            self._row_to_view(
                row,
                grants[ProductCollaborationID(row.oid)],
            )
            for row in rows
        ]

    async def _load_grants(
        self,
        collaboration_ids: list[ProductCollaborationID],
    ) -> dict[ProductCollaborationID, tuple[CollaborationGrantView, ...]]:
        if not collaboration_ids:
            return {}
        stmt = (
            sa.select(
                collaboration_grants_table.c.oid,
                collaboration_grants_table.c.collaboration_id,
                collaboration_grants_table.c.role_id,
                collaboration_grants_table.c.scope_type,
                collaboration_grants_table.c.scope_id,
                roles_table.c.name.label("role_name"),
            )
            .select_from(
                collaboration_grants_table.join(
                    roles_table,
                    collaboration_grants_table.c.role_id == roles_table.c.oid,
                ),
            )
            .where(
                collaboration_grants_table.c.collaboration_id.in_(
                    collaboration_ids,
                ),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        buckets: dict[
            ProductCollaborationID,
            list[CollaborationGrantView],
        ] = {cid: [] for cid in collaboration_ids}
        for row in rows:
            buckets[ProductCollaborationID(row.collaboration_id)].append(
                CollaborationGrantView(
                    oid=CollaborationGrantID(row.oid),
                    role_id=RoleID(row.role_id),
                    role_name=row.role_name,
                    scope_type=ScopeType(row.scope_type),
                    scope_id=row.scope_id,
                ),
            )
        return {cid: tuple(items) for cid, items in buckets.items()}

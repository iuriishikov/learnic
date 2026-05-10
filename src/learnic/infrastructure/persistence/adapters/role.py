from collections.abc import Sequence
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.role import (
    RoleGateway,
    RoleReader,
    RoleSaver,
    RoleView,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.role.ids import RoleID
from learnic.entities.role.models import Role
from learnic.entities.role.permissions import Permission
from learnic.entities.role.value_objects import PermissionSet
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.product_collaboration import (
    collaboration_grants_table,
    product_collaborations_table,
)
from learnic.infrastructure.persistence.models.role import (
    role_permissions_table,
    roles_table,
)


def _row_to_view(
    row: sa.Row[Any],
    permissions: frozenset[Permission],
) -> RoleView:
    return RoleView(
        oid=RoleID(row.oid),
        product_id=ProductID(row.product_id),
        name=row.name,
        description=row.description,
        position=row.position,
        permissions=permissions,
        created_by=UserID(row.created_by) if row.created_by else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class RoleMapperAlchemy(RoleGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: RoleID) -> Role | None:
        stmt = sa.select(Role).where(roles_table.c.oid == oid)
        role = (await self._session.execute(stmt)).scalar_one_or_none()
        if role is None:
            return None
        role.permissions = await self._load_permissions(oid)
        return role

    @override
    async def with_name_for_product(
        self,
        product_id: ProductID,
        name: str,
    ) -> Role | None:
        stmt = sa.select(Role).where(
            roles_table.c.product_id == product_id,
            roles_table.c.name == name,
        )
        role = (await self._session.execute(stmt)).scalar_one_or_none()
        if role is None:
            return None
        role.permissions = await self._load_permissions(role.oid)
        return role

    @override
    async def is_in_use(self, oid: RoleID) -> bool:
        # Only grants tied to a live collaboration count: DECLINED
        # and REVOKED are terminal audit rows whose grants linger
        # for history but no longer effect any permission. Without
        # this filter a once-invited-then-declined user would
        # block role deletion forever.
        stmt = (
            sa.select(collaboration_grants_table.c.oid)
            .select_from(
                collaboration_grants_table.join(
                    product_collaborations_table,
                    product_collaborations_table.c.oid
                    == collaboration_grants_table.c.collaboration_id,
                ),
            )
            .where(
                collaboration_grants_table.c.role_id == oid,
                product_collaborations_table.c.status.in_(
                    [
                        CollaborationStatus.PENDING_INVITE.value,
                        CollaborationStatus.ACTIVE.value,
                    ],
                ),
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).first() is not None

    @override
    async def delete(self, role: Role) -> None:
        # FK collaboration_grants.role_id is ON DELETE RESTRICT, so
        # any lingering grant from a DECLINED/REVOKED collaboration
        # would raise IntegrityError even though `is_in_use` already
        # reported the role as free. Purge those dead-collaboration
        # grants first so the role row can be removed.
        await self._session.execute(
            sa.delete(collaboration_grants_table).where(
                collaboration_grants_table.c.role_id == role.oid,
                collaboration_grants_table.c.collaboration_id.in_(
                    sa.select(product_collaborations_table.c.oid).where(
                        product_collaborations_table.c.status.in_(
                            [
                                CollaborationStatus.DECLINED.value,
                                CollaborationStatus.REVOKED.value,
                            ],
                        ),
                    ),
                ),
            ),
        )
        await self._session.delete(role)

    async def _load_permissions(self, role_id: RoleID) -> PermissionSet:
        stmt = sa.select(role_permissions_table.c.permission).where(
            role_permissions_table.c.role_id == role_id,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return PermissionSet(frozenset(Permission(p) for p in rows))


class RoleSaverAlchemy(RoleSaver):
    """SQL-backed :class:`RoleSaver`.

    The role's parent row is staged through the SA Unit of Work
    (``session.add(role)``); the permission rows go through
    :data:`role_permissions_table` directly because permissions
    are not entities. ``flush()`` is called to materialise the
    parent row's PK before inserting child rows that FK on it.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def save(self, role: Role) -> None:
        if role.permissions is None:
            msg = "Role.permissions must be set before saving"
            raise ValueError(msg)
        self._session.add(role)
        await self._session.flush()
        await self._insert_permissions(role.oid, role.permissions.permissions)

    @override
    async def replace_permissions(self, role: Role) -> None:
        if role.permissions is None:
            msg = "Role.permissions must be set before replacing"
            raise ValueError(msg)
        await self._session.execute(
            sa.delete(role_permissions_table).where(
                role_permissions_table.c.role_id == role.oid,
            ),
        )
        await self._insert_permissions(role.oid, role.permissions.permissions)

    async def _insert_permissions(
        self,
        role_id: RoleID,
        permissions: frozenset[Permission],
    ) -> None:
        if not permissions:
            return
        await self._session.execute(
            sa.insert(role_permissions_table),
            [
                {"role_id": role_id, "permission": permission.value}
                for permission in permissions
            ],
        )


class RoleReaderAlchemy(RoleReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: RoleID) -> RoleView | None:
        stmt = sa.select(roles_table).where(roles_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        permissions = await self._load_permissions([RoleID(row.oid)])
        return _row_to_view(row, permissions[RoleID(row.oid)])

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[RoleView]:
        stmt = (
            sa.select(roles_table)
            .where(roles_table.c.product_id == product_id)
            .order_by(
                roles_table.c.position.asc(),
                roles_table.c.created_at.asc(),
            )
        )
        rows = (await self._session.execute(stmt)).all()
        return await self._rows_to_views(rows)

    @override
    async def max_position_in_product(
        self,
        product_id: ProductID,
    ) -> int:
        stmt = sa.select(
            sa.func.coalesce(sa.func.max(roles_table.c.position), 0),
        ).where(roles_table.c.product_id == product_id)
        return int((await self._session.execute(stmt)).scalar_one())

    @override
    async def min_position_for_user(
        self,
        product_id: ProductID,
        user_id: UserID,
    ) -> int | None:
        # Walk active grants on the product scope and pick the
        # user's highest-rank role (lowest numerical position).
        from learnic.entities.product_collaboration.enums import (
            CollaborationStatus,
        )
        from learnic.entities.role.permissions import ScopeType
        from learnic.infrastructure.persistence.models.product_collaboration import (
            product_collaborations_table,
        )

        stmt = (
            sa.select(sa.func.min(roles_table.c.position))
            .select_from(
                product_collaborations_table.join(
                    collaboration_grants_table,
                    collaboration_grants_table.c.collaboration_id
                    == product_collaborations_table.c.oid,
                ).join(
                    roles_table,
                    roles_table.c.oid == collaboration_grants_table.c.role_id,
                ),
            )
            .where(
                product_collaborations_table.c.product_id == product_id,
                product_collaborations_table.c.collaborator_id == user_id,
                product_collaborations_table.c.status
                == CollaborationStatus.ACTIVE.value,
                collaboration_grants_table.c.scope_type == ScopeType.PRODUCT.value,
            )
        )
        value = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(value) if value is not None else None

    async def _rows_to_views(
        self,
        rows: Sequence[sa.Row[Any]],
    ) -> list[RoleView]:
        if not rows:
            return []
        ids = [RoleID(row.oid) for row in rows]
        permissions = await self._load_permissions(ids)
        return [_row_to_view(row, permissions[RoleID(row.oid)]) for row in rows]

    async def _load_permissions(
        self,
        role_ids: list[RoleID],
    ) -> dict[RoleID, frozenset[Permission]]:
        if not role_ids:
            return {}
        stmt = sa.select(
            role_permissions_table.c.role_id,
            role_permissions_table.c.permission,
        ).where(role_permissions_table.c.role_id.in_(role_ids))
        rows = (await self._session.execute(stmt)).all()
        result: dict[RoleID, set[Permission]] = {rid: set() for rid in role_ids}
        for row in rows:
            result[RoleID(row.role_id)].add(Permission(row.permission))
        return {rid: frozenset(perms) for rid, perms in result.items()}

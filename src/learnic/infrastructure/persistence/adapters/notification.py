from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.notifications.views import (
    ActorView,
    CategoryCount,
    InviteAcceptedView,
    InviteSentView,
    NotificationCounters,
    NotificationDetailsView,
    NotificationListPage,
    NotificationView,
    ProductRefView,
)
from learnic.entities.notification.details import (
    InviteAcceptedDetails,
    InviteSentDetails,
    NotificationDetails,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.notification import (
    notification_invite_accepted_table,
    notification_invite_sent_table,
    notifications_table,
)
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.user import users_table


class NotificationGatewayAlchemy(NotificationGateway):
    """Postgres implementation of :class:`NotificationGateway`.

    Inserts go through SA Core for both the parent and the subtype
    row inside the same caller transaction — the caller drives
    commit. ``flush()`` materialises the parent before the subtype
    insert so the composite ``(notification_id, kind)`` foreign key
    has a target. Loads rebuild :class:`Notification` from the
    parent row and delegate subtype hydration to the matching
    table.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def add(self, notification: Notification) -> None:
        await self._session.execute(
            sa.insert(notifications_table).values(
                oid=notification.oid,
                recipient_id=notification.recipient_id,
                kind=notification.kind.value,
                category=notification.category.value,
                actor_id=notification.actor_id,
                created_at=notification.created_at,
                read_at=notification.read_at,
            ),
        )
        await self._insert_subtype(notification)

    async def _insert_subtype(self, notification: Notification) -> None:
        details = notification.details
        if isinstance(details, InviteSentDetails):
            await self._session.execute(
                sa.insert(notification_invite_sent_table).values(
                    notification_id=notification.oid,
                    kind=notification.kind.value,
                    collaboration_id=details.collaboration_id,
                    product_id=details.product_id,
                ),
            )
            return
        if isinstance(details, InviteAcceptedDetails):
            await self._session.execute(
                sa.insert(notification_invite_accepted_table).values(
                    notification_id=notification.oid,
                    kind=notification.kind.value,
                    collaboration_id=details.collaboration_id,
                    product_id=details.product_id,
                    collaborator_id=details.collaborator_id,
                ),
            )
            return
        raise NotImplementedError(
            f"Unsupported notification details: {type(details).__name__}",
        )

    @override
    async def with_id(
        self,
        oid: NotificationID,
    ) -> Notification | None:
        stmt = sa.select(Notification).where(
            notifications_table.c.oid == oid,
        )
        notification = (
            await self._session.execute(stmt)
        ).scalar_one_or_none()
        if notification is None:
            return None
        notification.details = await self._load_details(
            notification.oid,
            notification.kind,
        )
        return notification

    async def _load_details(
        self,
        notification_id: NotificationID,
        kind: NotificationKind,
    ) -> NotificationDetails:
        if kind is NotificationKind.INVITE_SENT:
            row = (
                await self._session.execute(
                    sa.select(
                        notification_invite_sent_table.c.collaboration_id,
                        notification_invite_sent_table.c.product_id,
                    ).where(
                        notification_invite_sent_table.c.notification_id
                        == notification_id,
                    ),
                )
            ).one()
            return InviteSentDetails(
                collaboration_id=ProductCollaborationID(row.collaboration_id),
                product_id=ProductID(row.product_id),
            )
        if kind is NotificationKind.INVITE_ACCEPTED:
            row = (
                await self._session.execute(
                    sa.select(
                        notification_invite_accepted_table.c.collaboration_id,
                        notification_invite_accepted_table.c.product_id,
                        notification_invite_accepted_table.c.collaborator_id,
                    ).where(
                        notification_invite_accepted_table.c.notification_id
                        == notification_id,
                    ),
                )
            ).one()
            return InviteAcceptedDetails(
                collaboration_id=ProductCollaborationID(row.collaboration_id),
                product_id=ProductID(row.product_id),
                collaborator_id=UserID(row.collaborator_id),
            )
        raise NotImplementedError(f"Unknown notification kind: {kind!r}")

    @override
    async def update_read_state(self, notification: Notification) -> None:
        await self._session.execute(
            sa.update(notifications_table)
            .where(notifications_table.c.oid == notification.oid)
            .values(read_at=notification.read_at),
        )

    @override
    async def mark_all_read(self, recipient_id: object) -> int:
        result = await self._session.execute(
            sa.update(notifications_table)
            .where(
                notifications_table.c.recipient_id == recipient_id,
                notifications_table.c.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc)),
        )
        return result.rowcount or 0


class NotificationReaderAlchemy(NotificationReader):
    """Postgres-backed read-side for :class:`NotificationView`.

    Query strategy is two-shot: one paginated select on
    ``notifications`` joined with ``users`` (actor) for every base
    field, then a follow-up batched ``IN`` lookup per kind to
    hydrate the polymorphic subtype rows. Counter queries hit a
    grouped aggregate over the same recipient — no subtype joins,
    so they stay cheap.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def list_for(
        self,
        recipient_id: UserID,
        category: NotificationCategory | None,
        cursor: str | None,
        limit: int,
    ) -> NotificationListPage:
        stmt = self._select_with_actor().where(
            notifications_table.c.recipient_id == recipient_id,
        )
        if category is not None:
            stmt = stmt.where(notifications_table.c.category == category.value)
        if cursor is not None:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
            except ValueError:
                cursor_dt = None
            if cursor_dt is not None:
                stmt = stmt.where(
                    notifications_table.c.created_at < cursor_dt,
                )
        stmt = stmt.order_by(
            notifications_table.c.created_at.desc(),
            notifications_table.c.oid.desc(),
        ).limit(limit + 1)

        rows = (await self._session.execute(stmt)).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        if not rows:
            return NotificationListPage(items=(), next_cursor=None)

        details_by_id = await self._load_details_for_rows(rows)
        product_refs = await self._load_product_refs(rows, details_by_id)

        items = tuple(
            self._row_to_view(row, details_by_id, product_refs) for row in rows
        )
        next_cursor = (
            rows[-1].created_at.isoformat() if has_more else None
        )
        return NotificationListPage(items=items, next_cursor=next_cursor)

    @override
    async def with_id(
        self,
        recipient_id: UserID,
        oid: NotificationID,
    ) -> NotificationView | None:
        stmt = self._select_with_actor().where(
            notifications_table.c.oid == oid,
            notifications_table.c.recipient_id == recipient_id,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        details_by_id = await self._load_details_for_rows([row])
        product_refs = await self._load_product_refs([row], details_by_id)
        return self._row_to_view(row, details_by_id, product_refs)

    @override
    async def counters_for(
        self,
        recipient_id: UserID,
    ) -> NotificationCounters:
        unread_expr = sa.case(
            (notifications_table.c.read_at.is_(None), 1),
            else_=0,
        )
        stmt = (
            sa.select(
                notifications_table.c.category,
                sa.func.count().label("total"),
                sa.func.coalesce(sa.func.sum(unread_expr), 0).label("unread"),
            )
            .where(notifications_table.c.recipient_id == recipient_id)
            .group_by(notifications_table.c.category)
        )
        rows = (await self._session.execute(stmt)).all()
        per_cat = {NotificationCategory(row.category): row for row in rows}
        buckets = tuple(
            CategoryCount(
                category=cat,
                total=int(per_cat[cat].total) if cat in per_cat else 0,
                unread=int(per_cat[cat].unread) if cat in per_cat else 0,
            )
            for cat in NotificationCategory
        )
        total = sum(bucket.total for bucket in buckets)
        unread = sum(bucket.unread for bucket in buckets)
        return NotificationCounters(
            total=total,
            unread=unread,
            by_category=buckets,
        )

    def _select_with_actor(self) -> sa.Select[Any]:
        return sa.select(
            notifications_table.c.oid,
            notifications_table.c.recipient_id,
            notifications_table.c.kind,
            notifications_table.c.category,
            notifications_table.c.actor_id,
            notifications_table.c.created_at,
            notifications_table.c.read_at,
            users_table.c.first_name.label("actor_first_name"),
            users_table.c.last_name.label("actor_last_name"),
            users_table.c.patronymic.label("actor_patronymic"),
        ).select_from(
            notifications_table.outerjoin(
                users_table,
                notifications_table.c.actor_id == users_table.c.oid,
            ),
        )

    async def _load_details_for_rows(
        self,
        rows: Sequence[sa.Row[Any]],
    ) -> dict[UUID, NotificationDetails]:
        invite_sent_ids = [
            row.oid
            for row in rows
            if NotificationKind(row.kind) is NotificationKind.INVITE_SENT
        ]
        invite_accepted_ids = [
            row.oid
            for row in rows
            if NotificationKind(row.kind) is NotificationKind.INVITE_ACCEPTED
        ]
        result: dict[UUID, NotificationDetails] = {}

        if invite_sent_ids:
            sub_rows = (
                await self._session.execute(
                    sa.select(
                        notification_invite_sent_table.c.notification_id,
                        notification_invite_sent_table.c.collaboration_id,
                        notification_invite_sent_table.c.product_id,
                    ).where(
                        notification_invite_sent_table.c.notification_id.in_(
                            invite_sent_ids,
                        ),
                    ),
                )
            ).all()
            for sub in sub_rows:
                result[sub.notification_id] = InviteSentDetails(
                    collaboration_id=ProductCollaborationID(
                        sub.collaboration_id,
                    ),
                    product_id=ProductID(sub.product_id),
                )

        if invite_accepted_ids:
            sub_rows = (
                await self._session.execute(
                    sa.select(
                        notification_invite_accepted_table.c.notification_id,
                        notification_invite_accepted_table.c.collaboration_id,
                        notification_invite_accepted_table.c.product_id,
                        notification_invite_accepted_table.c.collaborator_id,
                    ).where(
                        notification_invite_accepted_table.c.notification_id.in_(
                            invite_accepted_ids,
                        ),
                    ),
                )
            ).all()
            for sub in sub_rows:
                result[sub.notification_id] = InviteAcceptedDetails(
                    collaboration_id=ProductCollaborationID(
                        sub.collaboration_id,
                    ),
                    product_id=ProductID(sub.product_id),
                    collaborator_id=UserID(sub.collaborator_id),
                )

        return result

    async def _load_product_refs(
        self,
        rows: Sequence[sa.Row[Any]],
        details_by_id: dict[UUID, NotificationDetails],
    ) -> dict[UUID, ProductRefView]:
        product_ids: set[UUID] = set()
        for row in rows:
            details = details_by_id.get(row.oid)
            if isinstance(details, (InviteSentDetails, InviteAcceptedDetails)):
                product_ids.add(details.product_id)
        if not product_ids:
            return {}
        prod_rows = (
            await self._session.execute(
                sa.select(
                    products_table.c.oid,
                    products_table.c.name,
                ).where(products_table.c.oid.in_(product_ids)),
            )
        ).all()
        return {
            prod.oid: ProductRefView(
                oid=ProductID(prod.oid),
                name=prod.name,
            )
            for prod in prod_rows
        }

    def _row_to_view(
        self,
        row: sa.Row[Any],
        details_by_id: dict[UUID, NotificationDetails],
        product_refs: dict[UUID, ProductRefView],
    ) -> NotificationView:
        kind = NotificationKind(row.kind)
        details = details_by_id.get(row.oid)
        details_view = self._build_details_view(details, row, product_refs)
        actor = self._build_actor(row)
        return NotificationView(
            oid=NotificationID(row.oid),
            recipient_id=UserID(row.recipient_id),
            kind=kind,
            category=NotificationCategory(row.category),
            actor=actor,
            created_at=row.created_at,
            read_at=row.read_at,
            details=details_view,
        )

    def _build_actor(self, row: sa.Row[Any]) -> ActorView | None:
        if row.actor_id is None:
            return None
        return ActorView(
            oid=UserID(row.actor_id),
            first_name=row.actor_first_name or "",
            last_name=row.actor_last_name or "",
            patronymic=row.actor_patronymic,
        )

    def _build_details_view(
        self,
        details: NotificationDetails | None,
        row: sa.Row[Any],
        product_refs: dict[UUID, ProductRefView],
    ) -> NotificationDetailsView:
        if isinstance(details, InviteSentDetails):
            product = product_refs.get(details.product_id) or ProductRefView(
                oid=details.product_id,
                name="",
            )
            return InviteSentView(
                collaboration_id=details.collaboration_id,
                product=product,
            )
        if isinstance(details, InviteAcceptedDetails):
            product = product_refs.get(details.product_id) or ProductRefView(
                oid=details.product_id,
                name="",
            )
            collaborator = ActorView(
                oid=details.collaborator_id,
                first_name="",
                last_name="",
                patronymic=None,
            )
            return InviteAcceptedView(
                collaboration_id=details.collaboration_id,
                product=product,
                collaborator=collaborator,
            )
        raise NotImplementedError(
            f"Cannot project notification {row.oid!r}",
        )

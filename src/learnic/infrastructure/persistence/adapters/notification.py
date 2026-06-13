import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Final, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.notifications.kind_spec import (
    NotificationKindRegistry,
    NotificationKindSpec,
    RefRequest,
    ResolvedRefs,
)
from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.notifications.views import (
    CategoryCount,
    CollaborationSnapshotView,
    GiftSnapshotView,
    NotificationCounters,
    NotificationListPage,
    NotificationView,
    ProductRefView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.notification.details import NotificationDetails
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.user.models import UserID
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notifications_table,
)
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.product_collaboration import (
    product_collaborations_table,
)
from learnic.infrastructure.persistence.models.product_gift import (
    product_gifts_table,
)
from learnic.infrastructure.persistence.models.refresh_token import (
    refresh_tokens_table,
)
from learnic.infrastructure.persistence.models.user import users_table

_logger = logging.getLogger(__name__)


def _persistence(
    spec: NotificationKindSpec[Any, Any],
) -> NotificationKindPersistence[Any]:
    """Narrow a registered spec to its persistence half.

    Concrete specs in :mod:`learnic.infrastructure.notifications.specs`
    implement both the application :class:`NotificationKindSpec` and
    the infrastructure :class:`NotificationKindPersistence`
    Protocols. The registry returns the application view; this
    cast surfaces the SA Core methods to the gateway / reader.
    """
    return cast("NotificationKindPersistence[Any]", spec)


class NotificationGatewayAlchemy(NotificationGateway):
    """Postgres implementation of :class:`NotificationGateway`.

    Inserts go through SA Core for both the parent and the subtype
    row inside the same caller transaction — the caller drives
    commit. Loads rebuild :class:`Notification` from the parent
    row and delegate subtype hydration through the kind spec
    registry, so adding a new kind never touches this class.
    """

    def __init__(
        self,
        session: AsyncSession,
        kind_registry: NotificationKindRegistry,
    ) -> None:
        self._session: Final = session
        self._kinds: Final = kind_registry

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
        spec = _persistence(
            self._kinds.by_details_type(type(notification.details)),
        )
        await self._session.execute(
            sa.insert(spec.table).values(
                spec.insert_values(notification, notification.details),
            ),
        )

    @override
    async def with_id(
        self,
        oid: NotificationID,
    ) -> Notification | None:
        stmt = sa.select(Notification).where(
            notifications_table.c.oid == oid,
        )
        notification = (await self._session.execute(stmt)).scalar_one_or_none()
        if notification is None:
            return None
        spec = _persistence(self._kinds.by_kind(notification.kind))
        row = (
            await self._session.execute(
                sa.select(*spec.load_columns()).where(
                    spec.table.c.notification_id == notification.oid,
                ),
            )
        ).one()
        notification.details = spec.row_to_details(row)
        return notification

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
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount) if rowcount else 0


class NotificationReaderAlchemy(NotificationReader):
    """Postgres-backed read-side for :class:`NotificationView`.

    Two-shot query: one paginated select on ``notifications``
    joined with ``users`` (actor) for every base field, then a
    follow-up batched ``IN`` lookup per kind to hydrate the
    polymorphic subtype rows. Counter queries hit a grouped
    aggregate over the same recipient — no subtype joins, so
    they stay cheap.

    Reference resolution (products, users, collaboration
    snapshots, ``MANAGE_COLLABORATORS`` flags) is centralised:
    every spec declares what its details point at via
    :meth:`NotificationKindSpec.references`, the reader merges
    those requests across the batch, runs one query per entity
    type, and lets each spec compose the final view via
    :meth:`NotificationKindSpec.to_view`. Adding a new kind never
    touches this class — only the spec.
    """

    def __init__(
        self,
        session: AsyncSession,
        authorizer: Authorizer,
        kind_registry: NotificationKindRegistry,
    ) -> None:
        self._session: Final = session
        self._authorizer: Final = authorizer
        self._kinds: Final = kind_registry

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
            parsed = _parse_cursor(cursor)
            if parsed is not None:
                cursor_dt, cursor_oid = parsed
                if cursor_oid is None:
                    stmt = stmt.where(
                        notifications_table.c.created_at < cursor_dt,
                    )
                else:
                    # Composite keyset matching the (created_at DESC,
                    # oid DESC) order, so notifications sharing the
                    # boundary ``created_at`` are not skipped.
                    stmt = stmt.where(
                        sa.tuple_(
                            notifications_table.c.created_at,
                            notifications_table.c.oid,
                        )
                        < sa.tuple_(cursor_dt, cursor_oid),
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
        refs = await self._resolve_refs(recipient_id, details_by_id)
        items = self._project_rows(rows, details_by_id, refs)
        if has_more:
            last = rows[-1]
            next_cursor = f"{last.created_at.isoformat()}|{last.oid}"
        else:
            next_cursor = None
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
        refs = await self._resolve_refs(recipient_id, details_by_id)
        return self._row_to_view(row, details_by_id, refs)

    @override
    async def list_invite_sent_for_collaboration(
        self,
        recipient_id: UserID,
        collaboration_id: ProductCollaborationID,
    ) -> tuple[NotificationView, ...]:
        invite_sent_spec = _persistence(
            self._kinds.by_kind(NotificationKind.INVITE_SENT),
        )
        stmt = (
            self._select_with_actor()
            .join(
                invite_sent_spec.table,
                invite_sent_spec.table.c.notification_id == notifications_table.c.oid,
            )
            .where(
                notifications_table.c.recipient_id == recipient_id,
                notifications_table.c.kind == NotificationKind.INVITE_SENT.value,
                invite_sent_spec.table.c.collaboration_id == collaboration_id,
            )
            .order_by(notifications_table.c.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return ()
        details_by_id = await self._load_details_for_rows(rows)
        refs = await self._resolve_refs(recipient_id, details_by_id)
        return self._project_rows(rows, details_by_id, refs)

    @override
    async def list_gift_received_for_gift(
        self,
        recipient_id: UserID,
        gift_id: ProductGiftID,
    ) -> tuple[NotificationView, ...]:
        gift_received_spec = _persistence(
            self._kinds.by_kind(NotificationKind.GIFT_RECEIVED),
        )
        stmt = (
            self._select_with_actor()
            .join(
                gift_received_spec.table,
                gift_received_spec.table.c.notification_id
                == notifications_table.c.oid,
            )
            .where(
                notifications_table.c.recipient_id == recipient_id,
                notifications_table.c.kind
                == NotificationKind.GIFT_RECEIVED.value,
                gift_received_spec.table.c.gift_id == gift_id,
            )
            .order_by(notifications_table.c.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return ()
        details_by_id = await self._load_details_for_rows(rows)
        refs = await self._resolve_refs(recipient_id, details_by_id)
        return self._project_rows(rows, details_by_id, refs)

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

    # --------------------------- internals --------------------------- #

    def _project_rows(
        self,
        rows: Sequence[sa.Row[Any]],
        details_by_id: dict[UUID, NotificationDetails],
        refs: ResolvedRefs,
    ) -> tuple[NotificationView, ...]:
        return tuple(
            view
            for view in (self._row_to_view(row, details_by_id, refs) for row in rows)
            if view is not None
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
            users_table.c.email.label("actor_email"),
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
        ids_by_kind: dict[NotificationKind, list[UUID]] = {}
        for row in rows:
            ids_by_kind.setdefault(NotificationKind(row.kind), []).append(row.oid)
        result: dict[UUID, NotificationDetails] = {}
        for kind, ids in ids_by_kind.items():
            spec = _persistence(self._kinds.by_kind(kind))
            sub_rows = (
                await self._session.execute(
                    sa.select(*spec.load_columns()).where(
                        spec.table.c.notification_id.in_(ids),
                    ),
                )
            ).all()
            for sub in sub_rows:
                result[sub.notification_id] = spec.row_to_details(sub)
        return result

    async def _resolve_refs(
        self,
        recipient_id: UserID,
        details_by_id: dict[UUID, NotificationDetails],
    ) -> ResolvedRefs:
        request = RefRequest.empty()
        for details in details_by_id.values():
            spec = self._kinds.by_details_type(type(details))
            request.merge(spec.references(details))
        products = await self._fetch_products(request.product_ids)
        users = await self._fetch_users(request.user_ids)
        collaborations = await self._fetch_collaborations(
            request.collaboration_ids,
        )
        gifts = await self._fetch_gifts(request.gift_ids)
        manage_perms = await self._fetch_manage_perms(
            recipient_id,
            request.products_needing_manage_perm,
        )
        session_active = await self._fetch_session_active(
            recipient_id,
            request.session_family_ids,
        )
        return ResolvedRefs(
            products=products,
            users=users,
            collaborations=collaborations,
            gifts=gifts,
            manage_perms=manage_perms,
            session_active=session_active,
        )

    async def _fetch_products(
        self,
        ids: set[ProductID],
    ) -> dict[ProductID, ProductRefView]:
        if not ids:
            return {}
        rows = (
            await self._session.execute(
                sa.select(
                    products_table.c.oid,
                    products_table.c.name,
                ).where(products_table.c.oid.in_(ids)),
            )
        ).all()
        return {
            ProductID(row.oid): ProductRefView(
                oid=ProductID(row.oid),
                name=row.name,
            )
            for row in rows
        }

    async def _fetch_users(
        self,
        ids: set[UserID],
    ) -> dict[UserID, UserRefView]:
        if not ids:
            return {}
        rows = (
            await self._session.execute(
                sa.select(
                    users_table.c.oid,
                    users_table.c.email,
                    users_table.c.first_name,
                    users_table.c.last_name,
                    users_table.c.patronymic,
                ).where(users_table.c.oid.in_(ids)),
            )
        ).all()
        return {
            UserID(row.oid): UserRefView(
                oid=UserID(row.oid),
                email=row.email or "",
                first_name=row.first_name or "",
                last_name=row.last_name or "",
                patronymic=row.patronymic,
            )
            for row in rows
        }

    async def _fetch_collaborations(
        self,
        ids: set[ProductCollaborationID],
    ) -> dict[ProductCollaborationID, CollaborationSnapshotView]:
        if not ids:
            return {}
        rows = (
            await self._session.execute(
                sa.select(
                    product_collaborations_table.c.oid,
                    product_collaborations_table.c.status,
                    product_collaborations_table.c.accepted_at,
                    product_collaborations_table.c.declined_at,
                    product_collaborations_table.c.revoked_at,
                    product_collaborations_table.c.invite_expires_at,
                ).where(
                    product_collaborations_table.c.oid.in_(ids),
                ),
            )
        ).all()
        return {
            ProductCollaborationID(row.oid): CollaborationSnapshotView(
                status=CollaborationStatus(row.status),
                accepted_at=row.accepted_at,
                declined_at=row.declined_at,
                revoked_at=row.revoked_at,
                invite_expires_at=row.invite_expires_at,
            )
            for row in rows
        }

    async def _fetch_gifts(
        self,
        ids: set[ProductGiftID],
    ) -> dict[ProductGiftID, GiftSnapshotView]:
        if not ids:
            return {}
        rows = (
            await self._session.execute(
                sa.select(
                    product_gifts_table.c.oid,
                    product_gifts_table.c.status,
                    product_gifts_table.c.accepted_at,
                    product_gifts_table.c.declined_at,
                    product_gifts_table.c.revoked_at,
                    product_gifts_table.c.invite_expires_at,
                ).where(
                    product_gifts_table.c.oid.in_(ids),
                ),
            )
        ).all()
        return {
            ProductGiftID(row.oid): GiftSnapshotView(
                status=GiftStatus(row.status),
                accepted_at=row.accepted_at,
                declined_at=row.declined_at,
                revoked_at=row.revoked_at,
                invite_expires_at=row.invite_expires_at,
            )
            for row in rows
        }

    async def _fetch_session_active(
        self,
        recipient_id: UserID,
        family_ids: set[UUID],
    ) -> dict[UUID, bool]:
        """Return a `family_id -> still-active?` map for the recipient.

        Active = a refresh-token row exists for the family that belongs
        to the recipient, has no ``revoked_at``, and has not expired.
        Anything else (revoked, expired, missing) maps to ``False`` so
        the panel can hide the "Logout from this device" CTA on cards
        whose session is already gone.
        """
        if not family_ids:
            return {}
        now = datetime.now(timezone.utc)
        rows = (
            await self._session.execute(
                sa.select(refresh_tokens_table.c.family_id)
                .where(
                    refresh_tokens_table.c.family_id.in_(family_ids),
                    refresh_tokens_table.c.user_id == recipient_id,
                    refresh_tokens_table.c.revoked_at.is_(None),
                    refresh_tokens_table.c.expires_at > now,
                )
                .distinct(),
            )
        ).all()
        active = {row.family_id for row in rows}
        return {family_id: family_id in active for family_id in family_ids}

    async def _fetch_manage_perms(
        self,
        recipient_id: UserID,
        product_ids: set[ProductID],
    ) -> dict[ProductID, bool]:
        # Single batched authorizer call instead of one
        # effective_permissions(...) per product (the former N+1 — each
        # call fanned out to ~4 queries).
        return await self._authorizer.manage_collaborators_for_products(
            recipient_id,
            product_ids,
        )

    def _row_to_view(
        self,
        row: sa.Row[Any],
        details_by_id: dict[UUID, NotificationDetails],
        refs: ResolvedRefs,
    ) -> NotificationView | None:
        kind = NotificationKind(row.kind)
        details = details_by_id.get(row.oid)
        if details is None:
            _logger.warning(
                "Skipping notification %s (%s): subtype row missing",
                row.oid,
                kind.value,
            )
            return None
        spec = self._kinds.by_kind(kind)
        details_view = spec.to_view(details, refs)
        return NotificationView(
            oid=NotificationID(row.oid),
            recipient_id=UserID(row.recipient_id),
            kind=kind,
            category=NotificationCategory(row.category),
            actor=_build_actor(row),
            created_at=row.created_at,
            read_at=row.read_at,
            details=details_view,
        )


def _build_actor(row: sa.Row[Any]) -> UserRefView | None:
    if row.actor_id is None:
        return None
    return UserRefView(
        oid=UserID(row.actor_id),
        email=row.actor_email or "",
        first_name=row.actor_first_name or "",
        last_name=row.actor_last_name or "",
        patronymic=row.actor_patronymic,
    )


def _parse_cursor(cursor: str) -> tuple[datetime, UUID | None] | None:
    """Decode a ``<created_at>|<oid>`` keyset cursor.

    Returns ``(created_at, oid)``. Tolerates a legacy
    ``created_at``-only cursor (no ``|``) by returning ``oid=None`` so
    in-flight clients holding an old cursor still paginate (on the
    coarse created_at boundary) rather than 500.
    """
    raw_dt, sep, raw_oid = cursor.partition("|")
    try:
        created_at = datetime.fromisoformat(raw_dt)
    except ValueError:
        return None
    if not sep:
        return (created_at, None)
    try:
        return (created_at, UUID(raw_oid))
    except ValueError:
        return None

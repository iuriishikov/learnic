import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.notifications.views import (
    AccessRevokedView,
    CategoryCount,
    CollaborationSnapshotView,
    InviteAcceptedView,
    InviteDeclinedView,
    InviteSentView,
    NotificationCounters,
    NotificationDetailsView,
    NotificationListPage,
    NotificationView,
    ProductRefView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.notification.details import (
    AccessRevokedDetails,
    InviteAcceptedDetails,
    InviteDeclinedDetails,
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
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.notification import (
    notification_access_revoked_table,
    notification_invite_accepted_table,
    notification_invite_declined_table,
    notification_invite_sent_table,
    notifications_table,
)
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.product_collaboration import (
    product_collaborations_table,
)
from learnic.infrastructure.persistence.models.user import users_table

_logger = logging.getLogger(__name__)


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
        if isinstance(details, InviteDeclinedDetails):
            await self._session.execute(
                sa.insert(notification_invite_declined_table).values(
                    notification_id=notification.oid,
                    kind=notification.kind.value,
                    collaboration_id=details.collaboration_id,
                    product_id=details.product_id,
                    decliner_id=details.decliner_id,
                ),
            )
            return
        if isinstance(details, AccessRevokedDetails):
            await self._session.execute(
                sa.insert(notification_access_revoked_table).values(
                    notification_id=notification.oid,
                    kind=notification.kind.value,
                    collaboration_id=details.collaboration_id,
                    product_id=details.product_id,
                    revoker_id=details.revoker_id,
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
        notification = (await self._session.execute(stmt)).scalar_one_or_none()
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
        if kind is NotificationKind.INVITE_DECLINED:
            row = (
                await self._session.execute(
                    sa.select(
                        notification_invite_declined_table.c.collaboration_id,
                        notification_invite_declined_table.c.product_id,
                        notification_invite_declined_table.c.decliner_id,
                    ).where(
                        notification_invite_declined_table.c.notification_id
                        == notification_id,
                    ),
                )
            ).one()
            return InviteDeclinedDetails(
                collaboration_id=ProductCollaborationID(row.collaboration_id),
                product_id=ProductID(row.product_id),
                decliner_id=UserID(row.decliner_id),
            )
        if kind is NotificationKind.ACCESS_REVOKED:
            row = (
                await self._session.execute(
                    sa.select(
                        notification_access_revoked_table.c.collaboration_id,
                        notification_access_revoked_table.c.product_id,
                        notification_access_revoked_table.c.revoker_id,
                    ).where(
                        notification_access_revoked_table.c.notification_id
                        == notification_id,
                    ),
                )
            ).one()
            return AccessRevokedDetails(
                collaboration_id=ProductCollaborationID(row.collaboration_id),
                product_id=ProductID(row.product_id),
                revoker_id=UserID(row.revoker_id),
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
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount) if rowcount else 0


class NotificationReaderAlchemy(NotificationReader):
    """Postgres-backed read-side for :class:`NotificationView`.

    Query strategy is two-shot: one paginated select on
    ``notifications`` joined with ``users`` (actor) for every base
    field, then a follow-up batched ``IN`` lookup per kind to
    hydrate the polymorphic subtype rows. Counter queries hit a
    grouped aggregate over the same recipient — no subtype joins,
    so they stay cheap.

    The reader also resolves the recipient's current
    ``MANAGE_COLLABORATORS`` permission against each referenced
    product via :class:`Authorizer` so the SPA can hide management
    CTAs (revoke / re-invite) for users who lost the permission
    after the notification was published.
    """

    def __init__(
        self,
        session: AsyncSession,
        authorizer: Authorizer,
    ) -> None:
        self._session: Final = session
        self._authorizer: Final = authorizer

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
        collab_refs = await self._load_collaboration_refs(details_by_id)
        user_refs = await self._load_user_refs(details_by_id)
        manage_perms = await self._load_manage_permissions(recipient_id, details_by_id)

        items = self._project_rows(
            rows,
            details_by_id,
            product_refs,
            collab_refs,
            user_refs,
            manage_perms,
        )
        next_cursor = rows[-1].created_at.isoformat() if has_more else None
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
        collab_refs = await self._load_collaboration_refs(details_by_id)
        user_refs = await self._load_user_refs(details_by_id)
        manage_perms = await self._load_manage_permissions(recipient_id, details_by_id)
        return self._row_to_view(
            row,
            details_by_id,
            product_refs,
            collab_refs,
            user_refs,
            manage_perms,
        )

    def _project_rows(
        self,
        rows: Sequence[sa.Row[Any]],
        details_by_id: dict[UUID, NotificationDetails],
        product_refs: dict[UUID, ProductRefView],
        collab_refs: dict[UUID, CollaborationSnapshotView],
        user_refs: dict[UUID, UserRefView],
        manage_perms: dict[UUID, bool],
    ) -> tuple[NotificationView, ...]:
        return tuple(
            view
            for view in (
                self._row_to_view(
                    row,
                    details_by_id,
                    product_refs,
                    collab_refs,
                    user_refs,
                    manage_perms,
                )
                for row in rows
            )
            if view is not None
        )

    @override
    async def list_invite_sent_for_collaboration(
        self,
        recipient_id: UserID,
        collaboration_id: ProductCollaborationID,
    ) -> tuple[NotificationView, ...]:
        stmt = (
            self._select_with_actor()
            .join(
                notification_invite_sent_table,
                notification_invite_sent_table.c.notification_id
                == notifications_table.c.oid,
            )
            .where(
                notifications_table.c.recipient_id == recipient_id,
                notifications_table.c.kind == NotificationKind.INVITE_SENT.value,
                notification_invite_sent_table.c.collaboration_id == collaboration_id,
            )
            .order_by(notifications_table.c.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return ()
        details_by_id = await self._load_details_for_rows(rows)
        product_refs = await self._load_product_refs(rows, details_by_id)
        collab_refs = await self._load_collaboration_refs(details_by_id)
        user_refs = await self._load_user_refs(details_by_id)
        manage_perms = await self._load_manage_permissions(recipient_id, details_by_id)
        return self._project_rows(
            rows,
            details_by_id,
            product_refs,
            collab_refs,
            user_refs,
            manage_perms,
        )

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
        invite_declined_ids = [
            row.oid
            for row in rows
            if NotificationKind(row.kind) is NotificationKind.INVITE_DECLINED
        ]
        access_revoked_ids = [
            row.oid
            for row in rows
            if NotificationKind(row.kind) is NotificationKind.ACCESS_REVOKED
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

        if invite_declined_ids:
            sub_rows = (
                await self._session.execute(
                    sa.select(
                        notification_invite_declined_table.c.notification_id,
                        notification_invite_declined_table.c.collaboration_id,
                        notification_invite_declined_table.c.product_id,
                        notification_invite_declined_table.c.decliner_id,
                    ).where(
                        notification_invite_declined_table.c.notification_id.in_(
                            invite_declined_ids,
                        ),
                    ),
                )
            ).all()
            for sub in sub_rows:
                result[sub.notification_id] = InviteDeclinedDetails(
                    collaboration_id=ProductCollaborationID(
                        sub.collaboration_id,
                    ),
                    product_id=ProductID(sub.product_id),
                    decliner_id=UserID(sub.decliner_id),
                )

        if access_revoked_ids:
            sub_rows = (
                await self._session.execute(
                    sa.select(
                        notification_access_revoked_table.c.notification_id,
                        notification_access_revoked_table.c.collaboration_id,
                        notification_access_revoked_table.c.product_id,
                        notification_access_revoked_table.c.revoker_id,
                    ).where(
                        notification_access_revoked_table.c.notification_id.in_(
                            access_revoked_ids,
                        ),
                    ),
                )
            ).all()
            for sub in sub_rows:
                result[sub.notification_id] = AccessRevokedDetails(
                    collaboration_id=ProductCollaborationID(
                        sub.collaboration_id,
                    ),
                    product_id=ProductID(sub.product_id),
                    revoker_id=UserID(sub.revoker_id),
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
            if isinstance(
                details,
                (
                    InviteSentDetails,
                    InviteAcceptedDetails,
                    InviteDeclinedDetails,
                    AccessRevokedDetails,
                ),
            ):
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

    async def _load_collaboration_refs(
        self,
        details_by_id: dict[UUID, NotificationDetails],
    ) -> dict[UUID, CollaborationSnapshotView]:
        collaboration_ids: set[UUID] = set()
        for details in details_by_id.values():
            if isinstance(
                details,
                (
                    InviteSentDetails,
                    InviteAcceptedDetails,
                    InviteDeclinedDetails,
                ),
            ):
                collaboration_ids.add(details.collaboration_id)
        if not collaboration_ids:
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
                    product_collaborations_table.c.oid.in_(collaboration_ids),
                ),
            )
        ).all()
        return {
            row.oid: CollaborationSnapshotView(
                status=CollaborationStatus(row.status),
                accepted_at=row.accepted_at,
                declined_at=row.declined_at,
                revoked_at=row.revoked_at,
                invite_expires_at=row.invite_expires_at,
            )
            for row in rows
        }

    async def _load_user_refs(
        self,
        details_by_id: dict[UUID, NotificationDetails],
    ) -> dict[UUID, UserRefView]:
        """Hydrate every user referenced inside the loaded details.

        Covers the ``collaborator_id`` from ``invite_accepted``, the
        ``decliner_id`` from ``invite_declined`` and the
        ``revoker_id`` from ``access_revoked`` in a single ``IN``
        lookup. The HTTP boundary (``UserRefSchema``) requires a
        non-empty ``full_name``, so a real DB row is mandatory —
        falling back to a stub user ref with empty name strings
        breaks Pydantic validation at the route.
        """
        user_ids: set[UUID] = set()
        for details in details_by_id.values():
            if isinstance(details, InviteAcceptedDetails):
                user_ids.add(details.collaborator_id)
            elif isinstance(details, InviteDeclinedDetails):
                user_ids.add(details.decliner_id)
            elif isinstance(details, AccessRevokedDetails):
                user_ids.add(details.revoker_id)
        if not user_ids:
            return {}
        rows = (
            await self._session.execute(
                sa.select(
                    users_table.c.oid,
                    users_table.c.email,
                    users_table.c.first_name,
                    users_table.c.last_name,
                    users_table.c.patronymic,
                ).where(users_table.c.oid.in_(user_ids)),
            )
        ).all()
        return {
            row.oid: UserRefView(
                oid=UserID(row.oid),
                email=row.email or "",
                first_name=row.first_name or "",
                last_name=row.last_name or "",
                patronymic=row.patronymic,
            )
            for row in rows
        }

    async def _load_manage_permissions(
        self,
        recipient_id: UserID,
        details_by_id: dict[UUID, NotificationDetails],
    ) -> dict[UUID, bool]:
        """Resolve ``MANAGE_COLLABORATORS`` per referenced product.

        Per-product check via :class:`Authorizer` — the SPA needs
        the flag only on cards that expose a management CTA
        (``invite_accepted`` revoke / ``invite_declined`` re-invite),
        so we only resolve it for products mentioned by those kinds.
        """
        product_ids: set[UUID] = set()
        for details in details_by_id.values():
            if isinstance(
                details,
                (InviteAcceptedDetails, InviteDeclinedDetails),
            ):
                product_ids.add(details.product_id)
        if not product_ids:
            return {}
        result: dict[UUID, bool] = {}
        for product_id in product_ids:
            permissions = await self._authorizer.effective_permissions(
                recipient_id,
                AuthzTarget.for_product(ProductID(product_id)),
            )
            result[product_id] = (
                permissions is not None
                and Permission.MANAGE_COLLABORATORS in permissions.permissions
            )
        return result

    def _row_to_view(
        self,
        row: sa.Row[Any],
        details_by_id: dict[UUID, NotificationDetails],
        product_refs: dict[UUID, ProductRefView],
        collab_refs: dict[UUID, CollaborationSnapshotView],
        user_refs: dict[UUID, UserRefView],
        manage_perms: dict[UUID, bool],
    ) -> NotificationView | None:
        kind = NotificationKind(row.kind)
        details = details_by_id.get(row.oid)
        details_view = self._build_details_view(
            details, row, product_refs, collab_refs, user_refs, manage_perms
        )
        if details_view is None:
            _logger.warning(
                "Skipping notification %s (%s): subtype row missing",
                row.oid,
                kind.value,
            )
            return None
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

    def _build_actor(self, row: sa.Row[Any]) -> UserRefView | None:
        if row.actor_id is None:
            return None
        return UserRefView(
            oid=UserID(row.actor_id),
            email=row.actor_email or "",
            first_name=row.actor_first_name or "",
            last_name=row.actor_last_name or "",
            patronymic=row.actor_patronymic,
        )

    def _build_details_view(
        self,
        details: NotificationDetails | None,
        row: sa.Row[Any],  # noqa: ARG002
        product_refs: dict[UUID, ProductRefView],
        collab_refs: dict[UUID, CollaborationSnapshotView],
        user_refs: dict[UUID, UserRefView],
        manage_perms: dict[UUID, bool],
    ) -> NotificationDetailsView | None:
        if isinstance(details, InviteSentDetails):
            product = product_refs.get(details.product_id) or ProductRefView(
                oid=details.product_id,
                name="",
            )
            return InviteSentView(
                collaboration_id=details.collaboration_id,
                product=product,
                collaboration=collab_refs.get(details.collaboration_id),
            )
        if isinstance(details, InviteAcceptedDetails):
            product = product_refs.get(details.product_id) or ProductRefView(
                oid=details.product_id,
                name="",
            )
            collaborator = user_refs.get(
                details.collaborator_id
            ) or _user_ref_placeholder(details.collaborator_id)
            return InviteAcceptedView(
                collaboration_id=details.collaboration_id,
                product=product,
                collaborator=collaborator,
                collaboration=collab_refs.get(details.collaboration_id),
                viewer_can_manage_collaborators=manage_perms.get(
                    details.product_id, False
                ),
            )
        if isinstance(details, InviteDeclinedDetails):
            product = product_refs.get(details.product_id) or ProductRefView(
                oid=details.product_id,
                name="",
            )
            decliner = user_refs.get(
                details.decliner_id
            ) or _user_ref_placeholder(details.decliner_id)
            return InviteDeclinedView(
                collaboration_id=details.collaboration_id,
                product=product,
                decliner=decliner,
                collaboration=collab_refs.get(details.collaboration_id),
                viewer_can_manage_collaborators=manage_perms.get(
                    details.product_id, False
                ),
            )
        if isinstance(details, AccessRevokedDetails):
            product = product_refs.get(details.product_id) or ProductRefView(
                oid=details.product_id,
                name="",
            )
            revoker = user_refs.get(
                details.revoker_id
            ) or _user_ref_placeholder(details.revoker_id)
            return AccessRevokedView(
                collaboration_id=details.collaboration_id,
                product=product,
                revoker=revoker,
            )
        return None


def _user_ref_placeholder(user_id: UserID) -> UserRefView:
    """Defensive fallback for a user row that vanished mid-flight.

    The HTTP boundary (``UserRefSchema``) requires a non-empty
    ``full_name``, so we must never produce empty name strings.
    Falling back to a single-character bullet keeps the schema
    happy and gives the SPA a recognisable placeholder for the
    rare race where a user was deleted between the notification
    insert and the read-time JOIN.
    """
    return UserRefView(
        oid=user_id,
        email="",
        first_name="—",
        last_name="",
        patronymic=None,
    )

"""Spec for ``invite_declined`` — invitee declined the invite."""

import uuid
from collections.abc import Sequence
from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.application.common.notifications.kind_spec import (
    NotificationKindSpec,
    RefRequest,
    ResolvedRefs,
)
from learnic.application.common.notifications.views import InviteDeclinedView
from learnic.entities.notification.details import InviteDeclinedDetails
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.notifications.specs._helpers import (
    actor_to_ws,
    collaboration_to_ws,
    deserialize_actor_required,
    deserialize_collaboration,
    deserialize_product,
    product_to_ws,
    serialize_actor,
    serialize_collaboration,
    serialize_product,
)
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notification_invite_declined_table,
)


@final
class InviteDeclinedSpec(
    NotificationKindSpec[InviteDeclinedDetails, InviteDeclinedView],
    NotificationKindPersistence[InviteDeclinedDetails],
):
    kind: ClassVar[NotificationKind] = NotificationKind.INVITE_DECLINED
    category: ClassVar[NotificationCategory] = NotificationCategory.TEACHING
    details_cls: ClassVar[type] = InviteDeclinedDetails
    view_cls: ClassVar[type] = InviteDeclinedView
    push_title: ClassVar[str] = "Invite declined"
    push_body: ClassVar[str] = "Your collaboration invite was declined."
    email_subject: ClassVar[str] = "Приглашение к совместной работе отклонено"
    email_body: ClassVar[str] = (
        "Ваше приглашение к совместной работе над продуктом было отклонено. "
        "Подробности — в панели уведомлений Learnic."
    )
    table: ClassVar[sa.Table] = notification_invite_declined_table

    @override
    def references(self, details: InviteDeclinedDetails) -> RefRequest:
        return RefRequest(
            product_ids={details.product_id},
            user_ids={details.decliner_id},
            collaboration_ids={details.collaboration_id},
            products_needing_manage_perm={details.product_id},
        )

    @override
    def to_view(
        self,
        details: InviteDeclinedDetails,
        refs: ResolvedRefs,
    ) -> InviteDeclinedView:
        return InviteDeclinedView(
            collaboration_id=details.collaboration_id,
            product=refs.product(details.product_id),
            decliner=refs.user(details.decliner_id),
            collaboration=refs.collaboration(details.collaboration_id),
            viewer_can_manage_collaborators=refs.can_manage(details.product_id),
        )

    @override
    def serialize_view(self, view: InviteDeclinedView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": serialize_product(view.product),
            "decliner": serialize_actor(view.decliner),
            "collaboration": serialize_collaboration(view.collaboration),
            "viewer_can_manage_collaborators": (view.viewer_can_manage_collaborators),
        }

    @override
    def deserialize_view(self, data: dict[str, Any]) -> InviteDeclinedView:
        return InviteDeclinedView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=deserialize_product(data["product"]),
            decliner=deserialize_actor_required(
                data["decliner"],
                "invite_declined",
            ),
            collaboration=deserialize_collaboration(data.get("collaboration")),
            viewer_can_manage_collaborators=bool(
                data.get("viewer_can_manage_collaborators", False),
            ),
        )

    @override
    def to_ws_dict(self, view: InviteDeclinedView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": product_to_ws(view.product),
            "decliner": actor_to_ws(view.decliner),
            "collaboration": collaboration_to_ws(view.collaboration),
            "viewer_can_manage_collaborators": (view.viewer_can_manage_collaborators),
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: InviteDeclinedDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "collaboration_id": details.collaboration_id,
            "product_id": details.product_id,
            "decliner_id": details.decliner_id,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.collaboration_id,
            self.table.c.product_id,
            self.table.c.decliner_id,
        )

    @override
    def row_to_details(self, row: sa.Row[Any]) -> InviteDeclinedDetails:
        return InviteDeclinedDetails(
            collaboration_id=ProductCollaborationID(row.collaboration_id),
            product_id=ProductID(row.product_id),
            decliner_id=UserID(row.decliner_id),
        )

"""Spec for ``invite_sent`` — recipient was invited to collaborate."""

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
from learnic.application.common.notifications.views import InviteSentView
from learnic.entities.notification.details import InviteSentDetails
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.infrastructure.notifications.specs._helpers import (
    collaboration_to_ws,
    deserialize_collaboration,
    deserialize_product,
    product_to_ws,
    serialize_collaboration,
    serialize_product,
)
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notification_invite_sent_table,
)


@final
class InviteSentSpec(
    NotificationKindSpec[InviteSentDetails, InviteSentView],
    NotificationKindPersistence[InviteSentDetails],
):
    kind: ClassVar[NotificationKind] = NotificationKind.INVITE_SENT
    category: ClassVar[NotificationCategory] = NotificationCategory.TEACHING
    details_cls: ClassVar[type] = InviteSentDetails
    view_cls: ClassVar[type] = InviteSentView
    push_title: ClassVar[str] = "New collaboration invite"
    push_body: ClassVar[str] = "You have been invited to collaborate on a product."
    email_subject: ClassVar[str] = "Приглашение к совместной работе на Learnic"
    email_body: ClassVar[str] = (
        "Вас пригласили в совместную работу над продуктом на платформе "
        "Learnic. Откройте панель уведомлений в приложении, чтобы принять "
        "или отклонить приглашение."
    )
    table: ClassVar[sa.Table] = notification_invite_sent_table

    @override
    def references(self, details: InviteSentDetails) -> RefRequest:
        return RefRequest(
            product_ids={details.product_id},
            collaboration_ids={details.collaboration_id},
        )

    @override
    def to_view(
        self,
        details: InviteSentDetails,
        refs: ResolvedRefs,
    ) -> InviteSentView:
        return InviteSentView(
            collaboration_id=details.collaboration_id,
            product=refs.product(details.product_id),
            collaboration=refs.collaboration(details.collaboration_id),
        )

    @override
    def serialize_view(self, view: InviteSentView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": serialize_product(view.product),
            "collaboration": serialize_collaboration(view.collaboration),
        }

    @override
    def deserialize_view(self, data: dict[str, Any]) -> InviteSentView:
        return InviteSentView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=deserialize_product(data["product"]),
            collaboration=deserialize_collaboration(data.get("collaboration")),
        )

    @override
    def to_ws_dict(self, view: InviteSentView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": product_to_ws(view.product),
            "collaboration": collaboration_to_ws(view.collaboration),
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: InviteSentDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "collaboration_id": details.collaboration_id,
            "product_id": details.product_id,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.collaboration_id,
            self.table.c.product_id,
        )

    @override
    def row_to_details(self, row: sa.Row[Any]) -> InviteSentDetails:
        return InviteSentDetails(
            collaboration_id=ProductCollaborationID(row.collaboration_id),
            product_id=ProductID(row.product_id),
        )

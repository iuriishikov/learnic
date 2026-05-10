"""Spec for ``access_revoked`` — recipient lost access to a product."""

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
from learnic.application.common.notifications.views import AccessRevokedView
from learnic.entities.notification.details import AccessRevokedDetails
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
    deserialize_actor_required,
    deserialize_product,
    product_to_ws,
    serialize_actor,
    serialize_product,
)
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notification_access_revoked_table,
)


@final
class AccessRevokedSpec(
    NotificationKindSpec[AccessRevokedDetails, AccessRevokedView],
    NotificationKindPersistence[AccessRevokedDetails],
):
    kind: ClassVar[NotificationKind] = NotificationKind.ACCESS_REVOKED
    category: ClassVar[NotificationCategory] = NotificationCategory.TEACHING
    details_cls: ClassVar[type] = AccessRevokedDetails
    view_cls: ClassVar[type] = AccessRevokedView
    push_title: ClassVar[str] = "Access revoked"
    push_body: ClassVar[str] = "Your access to a product was revoked."
    email_subject: ClassVar[str] = "Доступ к продукту отозван"
    email_body: ClassVar[str] = (
        "Ваш доступ к продукту в совместной работе был отозван. "
        "Подробности — в панели уведомлений Learnic."
    )
    table: ClassVar[sa.Table] = notification_access_revoked_table

    @override
    def references(self, details: AccessRevokedDetails) -> RefRequest:
        return RefRequest(
            product_ids={details.product_id},
            user_ids={details.revoker_id},
        )

    @override
    def to_view(
        self,
        details: AccessRevokedDetails,
        refs: ResolvedRefs,
    ) -> AccessRevokedView:
        return AccessRevokedView(
            collaboration_id=details.collaboration_id,
            product=refs.product(details.product_id),
            revoker=refs.user(details.revoker_id),
        )

    @override
    def serialize_view(self, view: AccessRevokedView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": serialize_product(view.product),
            "revoker": serialize_actor(view.revoker),
        }

    @override
    def deserialize_view(self, data: dict[str, Any]) -> AccessRevokedView:
        return AccessRevokedView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=deserialize_product(data["product"]),
            revoker=deserialize_actor_required(data["revoker"], "access_revoked"),
        )

    @override
    def to_ws_dict(self, view: AccessRevokedView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": product_to_ws(view.product),
            "revoker": actor_to_ws(view.revoker),
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: AccessRevokedDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "collaboration_id": details.collaboration_id,
            "product_id": details.product_id,
            "revoker_id": details.revoker_id,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.collaboration_id,
            self.table.c.product_id,
            self.table.c.revoker_id,
        )

    @override
    def row_to_details(self, row: sa.Row[Any]) -> AccessRevokedDetails:
        return AccessRevokedDetails(
            collaboration_id=ProductCollaborationID(row.collaboration_id),
            product_id=ProductID(row.product_id),
            revoker_id=UserID(row.revoker_id),
        )

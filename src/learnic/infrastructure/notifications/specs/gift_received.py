"""Spec for ``gift_received`` — recipient was gifted product access."""

import uuid
from collections.abc import Sequence
from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.application.common.notifications.channels import (
    ChannelPayload,
    InAppPayload,
    PushPayload,
)
from learnic.application.common.notifications.kind_spec import (
    NotificationKindSpec,
    RefRequest,
    ResolvedRefs,
)
from learnic.application.common.notifications.views import GiftReceivedView
from learnic.entities.notification.details import GiftReceivedDetails
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
    NotificationKind,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.infrastructure.notifications.specs._helpers import (
    deserialize_gift,
    deserialize_product,
    gift_to_ws,
    product_to_ws,
    serialize_gift,
    serialize_product,
)
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notification_gift_received_table,
)


@final
class GiftReceivedSpec(
    NotificationKindSpec[GiftReceivedDetails, GiftReceivedView],
    NotificationKindPersistence[GiftReceivedDetails],
):
    kind: ClassVar[NotificationKind] = NotificationKind.GIFT_RECEIVED
    category: ClassVar[NotificationCategory] = NotificationCategory.LEARNING
    details_cls: ClassVar[type] = GiftReceivedDetails
    view_cls: ClassVar[type] = GiftReceivedView
    push_title: ClassVar[str] = "Вам подарили курс"
    push_body: ClassVar[str] = (
        "Вам подарили доступ к курсу на Learnic. Откройте приложение, "
        "чтобы принять или отклонить подарок."
    )
    # Email for this kind is sent directly by the invite handler with
    # dedicated Accept / Decline buttons (see InviteGiftBy*Handler), so
    # the generic publisher email is suppressed via the render override
    # below to avoid a duplicate send. These ClassVars stay defined to
    # satisfy the Protocol contract.
    email_subject: ClassVar[str] = "Вам подарили курс на Learnic"
    email_body: ClassVar[str] = (
        "Вам подарили доступ к курсу на платформе Learnic."
    )
    table: ClassVar[sa.Table] = notification_gift_received_table

    @override
    def render(
        self,
        channel: NotificationChannel,
        view: GiftReceivedView,
    ) -> ChannelPayload | None:
        if channel is NotificationChannel.EMAIL:
            return None
        if channel is NotificationChannel.PUSH:
            return PushPayload(
                title=self.push_title,
                body=self.push_body,
                category=self.category.value,
            )
        if channel is NotificationChannel.IN_APP:
            return InAppPayload(view=view)
        return None

    @override
    def references(self, details: GiftReceivedDetails) -> RefRequest:
        return RefRequest(
            product_ids={details.product_id},
            gift_ids={details.gift_id},
        )

    @override
    def to_view(
        self,
        details: GiftReceivedDetails,
        refs: ResolvedRefs,
    ) -> GiftReceivedView:
        return GiftReceivedView(
            gift_id=details.gift_id,
            product=refs.product(details.product_id),
            gift=refs.gift(details.gift_id),
        )

    @override
    def serialize_view(self, view: GiftReceivedView) -> dict[str, Any]:
        return {
            "gift_id": str(view.gift_id),
            "product": serialize_product(view.product),
            "gift": serialize_gift(view.gift),
        }

    @override
    def deserialize_view(self, data: dict[str, Any]) -> GiftReceivedView:
        return GiftReceivedView(
            gift_id=ProductGiftID(uuid.UUID(data["gift_id"])),
            product=deserialize_product(data["product"]),
            gift=deserialize_gift(data.get("gift")),
        )

    @override
    def to_ws_dict(self, view: GiftReceivedView) -> dict[str, Any]:
        return {
            "gift_id": str(view.gift_id),
            "product": product_to_ws(view.product),
            "gift": gift_to_ws(view.gift),
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: GiftReceivedDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "gift_id": details.gift_id,
            "product_id": details.product_id,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.gift_id,
            self.table.c.product_id,
        )

    @override
    def row_to_details(self, row: sa.Row[Any]) -> GiftReceivedDetails:
        return GiftReceivedDetails(
            gift_id=ProductGiftID(row.gift_id),
            product_id=ProductID(row.product_id),
        )

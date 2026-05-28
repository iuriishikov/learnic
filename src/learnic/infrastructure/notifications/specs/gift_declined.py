"""Spec for ``gift_declined`` — recipient declined the gift."""

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
from learnic.application.common.notifications.views import GiftDeclinedView
from learnic.entities.notification.details import GiftDeclinedDetails
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.user.models import UserID
from learnic.infrastructure.notifications.specs._helpers import (
    actor_to_ws,
    deserialize_actor_required,
    deserialize_gift,
    deserialize_product,
    gift_to_ws,
    product_to_ws,
    serialize_actor,
    serialize_gift,
    serialize_product,
)
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notification_gift_declined_table,
)


@final
class GiftDeclinedSpec(
    NotificationKindSpec[GiftDeclinedDetails, GiftDeclinedView],
    NotificationKindPersistence[GiftDeclinedDetails],
):
    kind: ClassVar[NotificationKind] = NotificationKind.GIFT_DECLINED
    category: ClassVar[NotificationCategory] = NotificationCategory.TEACHING
    details_cls: ClassVar[type] = GiftDeclinedDetails
    view_cls: ClassVar[type] = GiftDeclinedView
    push_title: ClassVar[str] = "Подарок отклонён"
    push_body: ClassVar[str] = "Ваш подарок-доступ к курсу был отклонён."
    email_subject: ClassVar[str] = "Ваш подарок на Learnic отклонён"
    email_body: ClassVar[str] = (
        "Получатель отклонил подаренный вами доступ к курсу. "
        "Подробности — в панели уведомлений Learnic."
    )
    table: ClassVar[sa.Table] = notification_gift_declined_table

    @override
    def references(self, details: GiftDeclinedDetails) -> RefRequest:
        return RefRequest(
            product_ids={details.product_id},
            user_ids={details.decliner_id},
            gift_ids={details.gift_id},
        )

    @override
    def to_view(
        self,
        details: GiftDeclinedDetails,
        refs: ResolvedRefs,
    ) -> GiftDeclinedView:
        return GiftDeclinedView(
            gift_id=details.gift_id,
            product=refs.product(details.product_id),
            decliner=refs.user(details.decliner_id),
            gift=refs.gift(details.gift_id),
        )

    @override
    def serialize_view(self, view: GiftDeclinedView) -> dict[str, Any]:
        return {
            "gift_id": str(view.gift_id),
            "product": serialize_product(view.product),
            "decliner": serialize_actor(view.decliner),
            "gift": serialize_gift(view.gift),
        }

    @override
    def deserialize_view(self, data: dict[str, Any]) -> GiftDeclinedView:
        return GiftDeclinedView(
            gift_id=ProductGiftID(uuid.UUID(data["gift_id"])),
            product=deserialize_product(data["product"]),
            decliner=deserialize_actor_required(
                data["decliner"],
                "gift_declined",
            ),
            gift=deserialize_gift(data.get("gift")),
        )

    @override
    def to_ws_dict(self, view: GiftDeclinedView) -> dict[str, Any]:
        return {
            "gift_id": str(view.gift_id),
            "product": product_to_ws(view.product),
            "decliner": actor_to_ws(view.decliner),
            "gift": gift_to_ws(view.gift),
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: GiftDeclinedDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "gift_id": details.gift_id,
            "product_id": details.product_id,
            "decliner_id": details.decliner_id,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.gift_id,
            self.table.c.product_id,
            self.table.c.decliner_id,
        )

    @override
    def row_to_details(self, row: sa.Row[Any]) -> GiftDeclinedDetails:
        return GiftDeclinedDetails(
            gift_id=ProductGiftID(row.gift_id),
            product_id=ProductID(row.product_id),
            decliner_id=UserID(row.decliner_id),
        )

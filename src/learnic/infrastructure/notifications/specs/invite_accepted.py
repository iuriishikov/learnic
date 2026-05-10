"""Spec for ``invite_accepted`` — invitee accepted the invite."""

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
from learnic.application.common.notifications.views import InviteAcceptedView
from learnic.entities.notification.details import InviteAcceptedDetails
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
    notification_invite_accepted_table,
)


@final
class InviteAcceptedSpec(
    NotificationKindSpec[InviteAcceptedDetails, InviteAcceptedView],
    NotificationKindPersistence[InviteAcceptedDetails],
):
    kind: ClassVar[NotificationKind] = NotificationKind.INVITE_ACCEPTED
    category: ClassVar[NotificationCategory] = NotificationCategory.TEACHING
    details_cls: ClassVar[type] = InviteAcceptedDetails
    view_cls: ClassVar[type] = InviteAcceptedView
    push_title: ClassVar[str] = "Invite accepted"
    push_body: ClassVar[str] = "Your collaboration invite was accepted."
    email_subject: ClassVar[str] = "Приглашение к совместной работе принято"
    email_body: ClassVar[str] = (
        "Ваше приглашение к совместной работе над продуктом было принято. "
        "Подробности — в панели уведомлений Learnic."
    )
    table: ClassVar[sa.Table] = notification_invite_accepted_table

    @override
    def references(self, details: InviteAcceptedDetails) -> RefRequest:
        return RefRequest(
            product_ids={details.product_id},
            user_ids={details.collaborator_id},
            collaboration_ids={details.collaboration_id},
            products_needing_manage_perm={details.product_id},
        )

    @override
    def to_view(
        self,
        details: InviteAcceptedDetails,
        refs: ResolvedRefs,
    ) -> InviteAcceptedView:
        return InviteAcceptedView(
            collaboration_id=details.collaboration_id,
            product=refs.product(details.product_id),
            collaborator=refs.user(details.collaborator_id),
            collaboration=refs.collaboration(details.collaboration_id),
            viewer_can_manage_collaborators=refs.can_manage(details.product_id),
        )

    @override
    def serialize_view(self, view: InviteAcceptedView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": serialize_product(view.product),
            "collaborator": serialize_actor(view.collaborator),
            "collaboration": serialize_collaboration(view.collaboration),
            "viewer_can_manage_collaborators": (view.viewer_can_manage_collaborators),
        }

    @override
    def deserialize_view(self, data: dict[str, Any]) -> InviteAcceptedView:
        return InviteAcceptedView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=deserialize_product(data["product"]),
            collaborator=deserialize_actor_required(
                data["collaborator"],
                "invite_accepted",
            ),
            collaboration=deserialize_collaboration(data.get("collaboration")),
            viewer_can_manage_collaborators=bool(
                data.get("viewer_can_manage_collaborators", False),
            ),
        )

    @override
    def to_ws_dict(self, view: InviteAcceptedView) -> dict[str, Any]:
        return {
            "collaboration_id": str(view.collaboration_id),
            "product": product_to_ws(view.product),
            "collaborator": actor_to_ws(view.collaborator),
            "collaboration": collaboration_to_ws(view.collaboration),
            "viewer_can_manage_collaborators": (view.viewer_can_manage_collaborators),
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: InviteAcceptedDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "collaboration_id": details.collaboration_id,
            "product_id": details.product_id,
            "collaborator_id": details.collaborator_id,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.collaboration_id,
            self.table.c.product_id,
            self.table.c.collaborator_id,
        )

    @override
    def row_to_details(self, row: sa.Row[Any]) -> InviteAcceptedDetails:
        return InviteAcceptedDetails(
            collaboration_id=ProductCollaborationID(row.collaboration_id),
            product_id=ProductID(row.product_id),
            collaborator_id=UserID(row.collaborator_id),
        )

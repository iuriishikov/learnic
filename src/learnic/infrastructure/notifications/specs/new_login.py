"""Spec for ``new_login`` — successful login on the user's account."""

import uuid
from collections.abc import Sequence
from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.application.common.notifications.channels import ChannelPayload
from learnic.application.common.notifications.kind_spec import (
    NotificationKindSpec,
    RefRequest,
    ResolvedRefs,
)
from learnic.application.common.notifications.views import NewLoginView
from learnic.entities.notification.details import NewLoginDetails
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
    NotificationKind,
)
from learnic.entities.notification.models import Notification
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notification_new_login_table,
)


@final
class NewLoginSpec(
    NotificationKindSpec[NewLoginDetails, NewLoginView],
    NotificationKindPersistence[NewLoginDetails],
):
    kind: ClassVar[NotificationKind] = NotificationKind.NEW_LOGIN
    category: ClassVar[NotificationCategory] = NotificationCategory.SECURITY
    details_cls: ClassVar[type] = NewLoginDetails
    view_cls: ClassVar[type] = NewLoginView
    push_title: ClassVar[str] = "Новый вход в аккаунт"
    push_body: ClassVar[str] = (
        "На вашем аккаунте был выполнен вход. Если это были не вы, "
        "смените пароль и завершите активные сессии."
    )
    email_subject: ClassVar[str] = "Новый вход в аккаунт Learnic"
    email_body: ClassVar[str] = (
        "На вашем аккаунте Learnic был выполнен вход. Если это были "
        "не вы, смените пароль и завершите активные сессии в "
        "настройках безопасности."
    )
    table: ClassVar[sa.Table] = notification_new_login_table

    @override
    def render(
        self,
        channel: NotificationChannel,
        view: NewLoginView,
    ) -> ChannelPayload | None:
        """Deliver a new-login alert in-app + push only — never email.

        A message on every sign-in would be inbox noise; the signal
        belongs in the bell panel and an optional push. The ``email_*``
        copy above is kept ready should the policy be reverted, but the
        EMAIL channel is suppressed here (same pattern as
        ``gift_received``). PUSH / IN_APP fall through to the default
        rendering off the ``push_*`` ClassVars / view.
        """
        if channel is NotificationChannel.EMAIL:
            return None
        return super().render(channel, view)

    @override
    def references(self, details: NewLoginDetails) -> RefRequest:
        return RefRequest(session_family_ids={details.session_id})

    @override
    def to_view(
        self,
        details: NewLoginDetails,
        refs: ResolvedRefs,
    ) -> NewLoginView:
        return NewLoginView(
            device_label=details.device_label,
            user_agent=details.user_agent,
            ip_address=details.ip_address,
            session_id=details.session_id,
            session_revoked=not refs.is_session_active(details.session_id),
        )

    @override
    def serialize_view(self, view: NewLoginView) -> dict[str, Any]:
        return {
            "device_label": view.device_label,
            "user_agent": view.user_agent,
            "ip_address": view.ip_address,
            "session_id": str(view.session_id),
            "session_revoked": view.session_revoked,
        }

    @override
    def deserialize_view(self, data: dict[str, Any]) -> NewLoginView:
        return NewLoginView(
            device_label=data.get("device_label"),
            user_agent=data.get("user_agent"),
            ip_address=data.get("ip_address"),
            session_id=uuid.UUID(data["session_id"]),
            session_revoked=bool(data.get("session_revoked", True)),
        )

    @override
    def to_ws_dict(self, view: NewLoginView) -> dict[str, Any]:
        return {
            "device_label": view.device_label,
            "user_agent": view.user_agent,
            "ip_address": view.ip_address,
            "session_id": str(view.session_id),
            "session_revoked": view.session_revoked,
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: NewLoginDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "session_id": details.session_id,
            "device_label": details.device_label,
            "user_agent": details.user_agent,
            "ip_address": details.ip_address,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.session_id,
            self.table.c.device_label,
            self.table.c.user_agent,
            self.table.c.ip_address,
        )

    @override
    def row_to_details(self, row: sa.Row[Any]) -> NewLoginDetails:
        return NewLoginDetails(
            device_label=row.device_label,
            user_agent=row.user_agent,
            ip_address=row.ip_address,
            session_id=row.session_id,
        )

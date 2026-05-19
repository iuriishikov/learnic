"""Spec for ``storage_quota_warning`` — over-quota grace started."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.application.common.notifications.kind_spec import (
    NotificationKindSpec,
    RefRequest,
    ResolvedRefs,
)
from learnic.application.common.notifications.views import (
    StorageQuotaWarningView,
)
from learnic.entities.billing.ids import PlanCode
from learnic.entities.notification.details import (
    StorageQuotaWarningDetails,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.models import Notification
from learnic.infrastructure.notifications.specs._persistence import (
    NotificationKindPersistence,
)
from learnic.infrastructure.persistence.models.notification import (
    notification_storage_quota_warning_table,
)


@final
class StorageQuotaWarningSpec(
    NotificationKindSpec[
        StorageQuotaWarningDetails,
        StorageQuotaWarningView,
    ],
    NotificationKindPersistence[StorageQuotaWarningDetails],
):
    kind: ClassVar[NotificationKind] = (
        NotificationKind.STORAGE_QUOTA_WARNING
    )
    category: ClassVar[NotificationCategory] = NotificationCategory.FILES
    details_cls: ClassVar[type] = StorageQuotaWarningDetails
    view_cls: ClassVar[type] = StorageQuotaWarningView
    push_title: ClassVar[str] = "Превышен лимит хранилища"
    push_body: ClassVar[str] = (
        "Ваши файлы превышают лимит тарифа. Освободите место "
        "до окончания льготного периода, иначе самые свежие "
        "загрузки будут удалены."
    )
    email_subject: ClassVar[str] = "Файлы Learnic превышают тариф"
    email_body: ClassVar[str] = (
        "Суммарный размер файлов в ваших курсах превысил лимит "
        "тарифа. Чтобы избежать автоматического удаления самых "
        "свежих загрузок, освободите место или повысьте план "
        "до истечения льготного периода."
    )
    table: ClassVar[sa.Table] = notification_storage_quota_warning_table

    @override
    def references(
        self,
        details: StorageQuotaWarningDetails,
    ) -> RefRequest:
        # Self-contained — no external refs need resolving.
        return RefRequest()

    @override
    def to_view(
        self,
        details: StorageQuotaWarningDetails,
        refs: ResolvedRefs,  # noqa: ARG002
    ) -> StorageQuotaWarningView:
        return StorageQuotaWarningView(
            plan_code=details.plan_code,
            over_bytes=details.over_bytes,
            plan_limit_bytes=details.plan_limit_bytes,
            grace_until=details.grace_until,
        )

    @override
    def serialize_view(
        self,
        view: StorageQuotaWarningView,
    ) -> dict[str, Any]:
        return {
            "plan_code": view.plan_code,
            "over_bytes": view.over_bytes,
            "plan_limit_bytes": view.plan_limit_bytes,
            "grace_until": view.grace_until.isoformat(),
        }

    @override
    def deserialize_view(
        self,
        data: dict[str, Any],
    ) -> StorageQuotaWarningView:
        return StorageQuotaWarningView(
            plan_code=PlanCode(data["plan_code"]),
            over_bytes=int(data["over_bytes"]),
            plan_limit_bytes=int(data["plan_limit_bytes"]),
            grace_until=datetime.fromisoformat(data["grace_until"]),
        )

    @override
    def to_ws_dict(self, view: StorageQuotaWarningView) -> dict[str, Any]:
        return {
            "plan_code": view.plan_code,
            "over_bytes": view.over_bytes,
            "plan_limit_bytes": view.plan_limit_bytes,
            "grace_until": view.grace_until.isoformat(),
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: StorageQuotaWarningDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "plan_code": details.plan_code,
            "over_bytes": details.over_bytes,
            "plan_limit_bytes": details.plan_limit_bytes,
            "grace_until": details.grace_until,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.plan_code,
            self.table.c.over_bytes,
            self.table.c.plan_limit_bytes,
            self.table.c.grace_until,
        )

    @override
    def row_to_details(
        self,
        row: sa.Row[Any],
    ) -> StorageQuotaWarningDetails:
        return StorageQuotaWarningDetails(
            plan_code=PlanCode(row.plan_code),
            over_bytes=int(row.over_bytes),
            plan_limit_bytes=int(row.plan_limit_bytes),
            grace_until=row.grace_until,
        )

"""Spec for ``storage_quota_enforced`` — overflow soft-deleted."""

from collections.abc import Sequence
from typing import Any, ClassVar, final

import sqlalchemy as sa
from typing_extensions import override

from learnic.application.common.notifications.kind_spec import (
    NotificationKindSpec,
    RefRequest,
    ResolvedRefs,
)
from learnic.application.common.notifications.views import (
    StorageQuotaEnforcedView,
)
from learnic.entities.billing.ids import PlanCode
from learnic.entities.notification.details import (
    StorageQuotaEnforcedDetails,
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
    notification_storage_quota_enforced_table,
)


@final
class StorageQuotaEnforcedSpec(
    NotificationKindSpec[
        StorageQuotaEnforcedDetails,
        StorageQuotaEnforcedView,
    ],
    NotificationKindPersistence[StorageQuotaEnforcedDetails],
):
    kind: ClassVar[NotificationKind] = (
        NotificationKind.STORAGE_QUOTA_ENFORCED
    )
    category: ClassVar[NotificationCategory] = NotificationCategory.FILES
    details_cls: ClassVar[type] = StorageQuotaEnforcedDetails
    view_cls: ClassVar[type] = StorageQuotaEnforcedView
    push_title: ClassVar[str] = "Часть файлов удалена"
    push_body: ClassVar[str] = (
        "Льготный период истёк — часть файлов удалена для "
        "соответствия лимиту тарифа, включая медиа в опубликованных "
        "конспектах."
    )
    email_subject: ClassVar[str] = "Файлы удалены по лимиту тарифа"
    email_body: ClassVar[str] = (
        "Льготный период по превышению хранилища истёк. Часть файлов "
        "была удалена, чтобы привести занимаемое место к лимиту "
        "вашего текущего тарифа. Удаление могло затронуть и медиа в "
        "уже опубликованных конспектах — на их месте теперь заглушка. "
        "Восстановить файлы можно, обратившись в поддержку, если они "
        "ещё не очищены финальным сборщиком мусора."
    )
    table: ClassVar[sa.Table] = notification_storage_quota_enforced_table

    @override
    def references(
        self,
        details: StorageQuotaEnforcedDetails,
    ) -> RefRequest:
        return RefRequest()

    @override
    def to_view(
        self,
        details: StorageQuotaEnforcedDetails,
        refs: ResolvedRefs,  # noqa: ARG002
    ) -> StorageQuotaEnforcedView:
        return StorageQuotaEnforcedView(
            plan_code=details.plan_code,
            deleted_files_count=details.deleted_files_count,
            freed_bytes=details.freed_bytes,
        )

    @override
    def serialize_view(
        self,
        view: StorageQuotaEnforcedView,
    ) -> dict[str, Any]:
        return {
            "plan_code": view.plan_code,
            "deleted_files_count": view.deleted_files_count,
            "freed_bytes": view.freed_bytes,
        }

    @override
    def deserialize_view(
        self,
        data: dict[str, Any],
    ) -> StorageQuotaEnforcedView:
        return StorageQuotaEnforcedView(
            plan_code=PlanCode(data["plan_code"]),
            deleted_files_count=int(data["deleted_files_count"]),
            freed_bytes=int(data["freed_bytes"]),
        )

    @override
    def to_ws_dict(
        self,
        view: StorageQuotaEnforcedView,
    ) -> dict[str, Any]:
        return {
            "plan_code": view.plan_code,
            "deleted_files_count": view.deleted_files_count,
            "freed_bytes": view.freed_bytes,
        }

    @override
    def insert_values(
        self,
        notification: Notification,
        details: StorageQuotaEnforcedDetails,
    ) -> dict[str, Any]:
        return {
            "notification_id": notification.oid,
            "kind": notification.kind.value,
            "plan_code": details.plan_code,
            "deleted_files_count": details.deleted_files_count,
            "freed_bytes": details.freed_bytes,
        }

    @override
    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        return (
            self.table.c.notification_id,
            self.table.c.plan_code,
            self.table.c.deleted_files_count,
            self.table.c.freed_bytes,
        )

    @override
    def row_to_details(
        self,
        row: sa.Row[Any],
    ) -> StorageQuotaEnforcedDetails:
        return StorageQuotaEnforcedDetails(
            plan_code=PlanCode(row.plan_code),
            deleted_files_count=int(row.deleted_files_count),
            freed_bytes=int(row.freed_bytes),
        )

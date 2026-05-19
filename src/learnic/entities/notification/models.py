import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.billing.ids import PlanCode
from learnic.entities.notification.details import (
    AccessRevokedDetails,
    InviteAcceptedDetails,
    InviteDeclinedDetails,
    InviteSentDetails,
    NewLoginDetails,
    NotificationDetails,
    StorageQuotaEnforcedDetails,
    StorageQuotaWarningDetails,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.errors import AlreadyReadError
from learnic.entities.notification.ids import NotificationID
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


@dataclass
class Notification(BaseEntity[NotificationID]):
    """A single in-app notification addressed to one user.

    The base row carries the fields every notification needs —
    recipient, discriminator (``kind``), tab grouping
    (``category``), actor, timestamps. The polymorphic body lives
    in :attr:`details`, mapped to a subtype table picked by ``kind``.

    ``read_at = None`` means unread (rendered as the blue dot in
    the panel). Marking idempotency is enforced at the domain level
    via :class:`AlreadyReadError`; the command handler translates
    it to a no-op for clients.
    """

    recipient_id: UserID
    kind: NotificationKind
    category: NotificationCategory
    actor_id: UserID | None
    created_at: datetime
    read_at: datetime | None
    details: NotificationDetails = field(
        default_factory=NotificationDetails,
    )

    def mark_read(self, *, now: datetime | None = None) -> None:
        if self.read_at is not None:
            raise AlreadyReadError
        self.read_at = now or datetime.now(timezone.utc)

    @classmethod
    def for_invite_sent(
        cls,
        *,
        recipient_id: UserID,
        actor_id: UserID,
        collaboration_id: ProductCollaborationID,
        product_id: ProductID,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=NotificationID(uuid.uuid4()),
            recipient_id=recipient_id,
            kind=NotificationKind.INVITE_SENT,
            category=NotificationCategory.TEACHING,
            actor_id=actor_id,
            created_at=moment,
            read_at=None,
            details=InviteSentDetails(
                collaboration_id=collaboration_id,
                product_id=product_id,
            ),
        )

    @classmethod
    def for_invite_accepted(
        cls,
        *,
        recipient_id: UserID,
        actor_id: UserID,
        collaboration_id: ProductCollaborationID,
        product_id: ProductID,
        collaborator_id: UserID,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=NotificationID(uuid.uuid4()),
            recipient_id=recipient_id,
            kind=NotificationKind.INVITE_ACCEPTED,
            category=NotificationCategory.TEACHING,
            actor_id=actor_id,
            created_at=moment,
            read_at=None,
            details=InviteAcceptedDetails(
                collaboration_id=collaboration_id,
                product_id=product_id,
                collaborator_id=collaborator_id,
            ),
        )

    @classmethod
    def for_invite_declined(
        cls,
        *,
        recipient_id: UserID,
        actor_id: UserID,
        collaboration_id: ProductCollaborationID,
        product_id: ProductID,
        decliner_id: UserID,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=NotificationID(uuid.uuid4()),
            recipient_id=recipient_id,
            kind=NotificationKind.INVITE_DECLINED,
            category=NotificationCategory.TEACHING,
            actor_id=actor_id,
            created_at=moment,
            read_at=None,
            details=InviteDeclinedDetails(
                collaboration_id=collaboration_id,
                product_id=product_id,
                decliner_id=decliner_id,
            ),
        )

    @classmethod
    def for_access_revoked(
        cls,
        *,
        recipient_id: UserID,
        actor_id: UserID,
        collaboration_id: ProductCollaborationID,
        product_id: ProductID,
        revoker_id: UserID,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=NotificationID(uuid.uuid4()),
            recipient_id=recipient_id,
            kind=NotificationKind.ACCESS_REVOKED,
            category=NotificationCategory.TEACHING,
            actor_id=actor_id,
            created_at=moment,
            read_at=None,
            details=AccessRevokedDetails(
                collaboration_id=collaboration_id,
                product_id=product_id,
                revoker_id=revoker_id,
            ),
        )

    @classmethod
    def for_storage_quota_warning(
        cls,
        *,
        recipient_id: UserID,
        plan_code: PlanCode,
        over_bytes: int,
        plan_limit_bytes: int,
        grace_until: datetime,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=NotificationID(uuid.uuid4()),
            recipient_id=recipient_id,
            kind=NotificationKind.STORAGE_QUOTA_WARNING,
            category=NotificationCategory.FILES,
            actor_id=None,
            created_at=moment,
            read_at=None,
            details=StorageQuotaWarningDetails(
                plan_code=plan_code,
                over_bytes=over_bytes,
                plan_limit_bytes=plan_limit_bytes,
                grace_until=grace_until,
            ),
        )

    @classmethod
    def for_storage_quota_enforced(
        cls,
        *,
        recipient_id: UserID,
        plan_code: PlanCode,
        deleted_files_count: int,
        freed_bytes: int,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=NotificationID(uuid.uuid4()),
            recipient_id=recipient_id,
            kind=NotificationKind.STORAGE_QUOTA_ENFORCED,
            category=NotificationCategory.FILES,
            actor_id=None,
            created_at=moment,
            read_at=None,
            details=StorageQuotaEnforcedDetails(
                plan_code=plan_code,
                deleted_files_count=deleted_files_count,
                freed_bytes=freed_bytes,
            ),
        )

    @classmethod
    def for_new_login(
        cls,
        *,
        recipient_id: UserID,
        session_id: uuid.UUID,
        device_label: str | None,
        user_agent: str | None,
        ip_address: str | None,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=NotificationID(uuid.uuid4()),
            recipient_id=recipient_id,
            kind=NotificationKind.NEW_LOGIN,
            category=NotificationCategory.SECURITY,
            actor_id=None,
            created_at=moment,
            read_at=None,
            details=NewLoginDetails(
                device_label=device_label,
                user_agent=user_agent,
                ip_address=ip_address,
                session_id=session_id,
            ),
        )

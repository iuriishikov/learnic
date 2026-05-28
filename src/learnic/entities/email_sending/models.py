import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from typing_extensions import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.email_sending.ids import EmailSendingID
from learnic.entities.user.models import UserID


@dataclass
class EmailSending(BaseEntity[EmailSendingID]):
    """Audit row for a single user-initiated outbound email.

    One row is written every time an authenticated actor triggers a
    transactional email (collaboration invite, gift, revoke notice).
    The table is both the source of truth for the per-user send rate
    limit — counted over ``EMAIL_SEND_RATE_LIMIT_WINDOW`` — and an
    audit trail of who caused which email to be sent.

    ``ip`` is captured for abuse forensics only; it is **never** used
    as a rate-limit key, so users sharing one VPN / NAT egress are
    billed independently and never blocked for each other's sends.
    """

    actor_id: UserID
    recipient: str
    ip: str | None
    sent_at: datetime

    @classmethod
    def record(
        cls,
        *,
        actor_id: UserID,
        recipient: str,
        ip: str | None,
    ) -> Self:
        """Create a send record stamped at the current UTC instant.

        Args:
            actor_id: Authenticated user who triggered the email.
            recipient: Destination email address (audit only).
            ip: Originating client IP, or ``None`` if undetermined.
        """
        return cls(
            oid=EmailSendingID(uuid.uuid4()),
            actor_id=actor_id,
            recipient=recipient,
            ip=ip,
            sent_at=datetime.now(timezone.utc),
        )

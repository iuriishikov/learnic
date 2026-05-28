from datetime import datetime, timezone
from typing import Final, final

from learnic.application.common.errors import (
    EmailSendRateLimitExceededError,
)
from learnic.application.common.persistence.email_sending import (
    EmailSendingGateway,
)
from learnic.application.common.persistence.transaction import EntitySaver
from learnic.entities.email_sending.constants import (
    EMAIL_SEND_RATE_LIMIT_WINDOW,
    IP_MAX_LEN,
    MAX_EMAILS_PER_USER,
)
from learnic.entities.email_sending.models import EmailSending
from learnic.entities.user.models import UserID


@final
class EmailSendRateLimiter:
    """Per-user cap on outbound, user-initiated transactional email.

    Handlers call :meth:`register` for every email an authenticated
    actor triggers, *before* committing their transaction. The limiter
    serialises per actor with an advisory lock, counts the actor's
    sends in the rolling ``EMAIL_SEND_RATE_LIMIT_WINDOW``, refuses once
    ``MAX_EMAILS_PER_USER`` is reached, and otherwise logs the send.

    Recording the send inside the caller's transaction is deliberate:
    a rolled-back action leaves no phantom log row, and the advisory
    lock closes the check-then-insert race (two concurrent sends can
    no longer both read the same count and both slip past the cap).

    The limit is keyed strictly on ``actor_id`` — never on IP — so a
    pool of users sharing one VPN / NAT egress are billed
    independently. ``ip`` is recorded for forensics only.
    """

    def __init__(
        self,
        gateway: EmailSendingGateway,
        entity_saver: EntitySaver,
    ) -> None:
        self._gateway: Final = gateway
        self._entity_saver: Final = entity_saver

    async def register(
        self,
        *,
        actor_id: UserID,
        recipient: str,
        ip: str | None,
    ) -> None:
        """Record one send by ``actor_id``, or refuse if over the cap.

        Must be called before the caller commits, so the recorded row
        shares the action's transaction and the advisory lock is held
        across the check-then-insert.

        Args:
            actor_id: Authenticated user who triggered the email.
            recipient: Destination address (audit only).
            ip: Originating client IP, truncated to ``IP_MAX_LEN``;
                ``None`` when it could not be determined. Logged for
                forensics, never used as a limit key.

        Raises:
            EmailSendRateLimitExceededError: The actor has already
                sent ``MAX_EMAILS_PER_USER`` emails within
                ``EMAIL_SEND_RATE_LIMIT_WINDOW``; surfaces as HTTP 429.
        """
        await self._gateway.acquire_actor_lock(actor_id)
        since = datetime.now(timezone.utc) - EMAIL_SEND_RATE_LIMIT_WINDOW
        sent = await self._gateway.count_since(actor_id, since)
        if sent >= MAX_EMAILS_PER_USER:
            raise EmailSendRateLimitExceededError(
                actor_id=actor_id,
                limit=MAX_EMAILS_PER_USER,
                retry_after_seconds=int(
                    EMAIL_SEND_RATE_LIMIT_WINDOW.total_seconds(),
                ),
            )
        self._entity_saver.add_one(
            EmailSending.record(
                actor_id=actor_id,
                recipient=recipient,
                ip=ip[:IP_MAX_LEN] if ip is not None else None,
            ),
        )

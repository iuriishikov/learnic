"""TaskIQ handler for delivering Web Push to all of a user's subscriptions.

Triggered by :class:`TaskScheduler.schedule_send_web_push`. The
handler resolves the recipient's subscriptions, applies the
notification preferences (unless explicitly bypassed by the
caller, e.g. for the in-app "Send test push" button), and ships
the payload through :class:`PushSender` for each row in parallel.
Endpoints that come back as ``Gone`` are dropped from the
gateway so future deliveries skip them.
"""

import asyncio
import logging
from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.common.notification_preferences.reader import (
    NotificationPreferencesReader,
)
from learnic.application.common.push.gateway import PushSubscriptionGateway
from learnic.application.common.push.payload import PushPayload
from learnic.application.common.push.sender import PushSender
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.tasks.broker import broker

_logger = logging.getLogger(__name__)


@broker.task
@inject(patch_module=True)
async def send_web_push_task(
    user_id: UUID,
    title: str,
    body: str,
    url: str | None,
    tag: str | None,
    icon: str | None,
    category: str | None,
    bypass_preferences: bool,
    gateway: FromDishka[PushSubscriptionGateway],
    sender: FromDishka[PushSender],
    preferences: FromDishka[NotificationPreferencesReader],
    transaction: FromDishka[Transaction],
) -> None:
    """Fan out a Web Push to every subscription of ``user_id``.

    Args:
        user_id: Recipient user UUID.
        title: System banner title.
        body: System banner body text.
        url: Optional click target — opened by the SW on click.
        tag: Optional notification tag for in-place replacement.
        icon: Optional icon URL for the system banner.
        category: ``NotificationCategory`` value for preference
            checks; ``None`` disables the check (used for system
            messages that ignore opt-outs).
        bypass_preferences: ``True`` for the manual "Send test"
            path — skips the per-category opt-in check entirely.
        gateway: Injected push-subscription store.
        sender: Injected push transport.
        preferences: Injected reader of notification preferences.
        transaction: Injected transaction handle for cleanup commits.
    """
    typed_user_id = UserID(user_id)
    if not bypass_preferences and category is not None:
        try:
            cat = NotificationCategory(category)
        except ValueError:
            _logger.warning(
                "send_web_push_task: unknown category %r; dropping",
                category,
            )
            return
        enabled = await preferences.is_channel_enabled(
            typed_user_id,
            NotificationChannel.PUSH,
            cat,
        )
        if not enabled:
            return

    subscriptions = await gateway.list_for_user(typed_user_id)
    if not subscriptions:
        _logger.info(
            "Web Push: no subscriptions for user %s; nothing to deliver",
            typed_user_id,
        )
        return

    payload = PushPayload(
        title=title,
        body=body,
        url=url,
        tag=tag,
        icon=icon,
    )

    deliveries = await asyncio.gather(
        *(sender.send(sub, payload) for sub in subscriptions),
        return_exceptions=False,
    )

    gone_endpoints = [
        sub.endpoint
        for sub, result in zip(subscriptions, deliveries, strict=True)
        if result.is_gone
    ]
    if gone_endpoints:
        for endpoint in gone_endpoints:
            await gateway.delete_by_endpoint(endpoint)
        await transaction.commit()
        _logger.info(
            "Web Push: cleaned %d expired subscriptions for user %s",
            len(gone_endpoints),
            typed_user_id,
        )

    delivered = sum(
        1
        for r in deliveries
        if not r.is_gone and (r.status_code is None or r.status_code < 300)
    )
    _logger.info(
        "Web Push: user=%s subs=%d delivered=%d gone=%d failed=%d",
        typed_user_id,
        len(subscriptions),
        delivered,
        len(gone_endpoints),
        len(subscriptions) - delivered - len(gone_endpoints),
    )

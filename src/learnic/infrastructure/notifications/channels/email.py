import logging
from typing import Final, final

from typing_extensions import override

from learnic.application.common.notifications.channels import (
    ChannelPayload,
    DeliveryChannel,
    EmailPayload,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.notification.enums import NotificationChannel
from learnic.entities.user.models import User

_logger = logging.getLogger(__name__)


@final
class EmailChannel(DeliveryChannel):
    """Email delivery channel — enqueues a ``schedule_send_email`` task."""

    name = NotificationChannel.EMAIL

    def __init__(self, scheduler: TaskScheduler) -> None:
        self._scheduler: Final = scheduler

    @override
    async def deliver(
        self,
        recipient: User,
        payload: ChannelPayload,
    ) -> None:
        if not isinstance(payload, EmailPayload):
            return
        try:
            await self._scheduler.schedule_send_email(
                to=recipient.email.value,
                subject=payload.subject,
                components=payload.components,
            )
        except Exception:
            _logger.exception(
                "EmailChannel delivery failed for recipient %s",
                recipient.oid,
            )

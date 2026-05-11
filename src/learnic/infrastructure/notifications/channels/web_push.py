import logging
from typing import Final, final

from typing_extensions import override

from learnic.application.common.notifications.channels import (
    ChannelPayload,
    DeliveryChannel,
    PushPayload,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.notification.enums import NotificationChannel
from learnic.entities.user.models import User

_logger = logging.getLogger(__name__)


@final
class WebPushChannel(DeliveryChannel):
    """Web Push delivery channel — enqueues a ``schedule_send_web_push`` task.

    The worker re-checks the user's preference at consume time
    (defence in depth), so a stale enqueue can't bypass an opt-out
    flipped between commit and delivery. The category is carried on
    the task so that re-check stays accurate.
    """

    name = NotificationChannel.PUSH

    def __init__(self, scheduler: TaskScheduler) -> None:
        self._scheduler: Final = scheduler

    @override
    async def deliver(
        self,
        recipient: User,
        payload: ChannelPayload,
    ) -> None:
        if not isinstance(payload, PushPayload):
            return
        try:
            await self._scheduler.schedule_send_web_push(
                user_id=recipient.oid,
                title=payload.title,
                body=payload.body,
                url=payload.url,
                icon=payload.icon,
                category=payload.category,
                # The test-send admin path uses the scheduler directly
                # with ``bypass_preferences=True``; channel-driven
                # fan-outs always respect preferences.
                bypass_preferences=False,
            )
        except Exception:
            _logger.exception(
                "WebPushChannel delivery failed for recipient %s",
                recipient.oid,
            )

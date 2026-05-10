from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.notification.enums import NotificationCategory
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SendPushToUserCommand:
    """Inputs for the generic ``POST /push/send`` endpoint.

    The endpoint exists so other backend services (or admin
    tooling) can deliver a Web Push to a known user without
    creating a corresponding in-app notification row. ``category``
    is required so :class:`NotificationPreferences` is applied —
    pushes outside the recipient's enabled categories are dropped
    by the worker before any HTTP delivery is attempted.
    """

    actor_id: UserID
    target_user_id: UserID
    category: NotificationCategory
    title: str
    body: str
    url: str | None
    tag: str | None
    icon: str | None


@final
class SendPushToUserCommandHandler:
    """Schedule a Web Push for an arbitrary recipient with full pref check.

    The caller's identity is captured for audit purposes only;
    any user can request a push to themselves, and admin scopes
    govern whether the route accepts ``target_user_id != actor_id``
    at the HTTP layer. Preference enforcement happens inside the
    worker so a long enqueue queue can't bypass a user-side opt-out
    issued mid-flight.
    """

    def __init__(self, scheduler: TaskScheduler) -> None:
        self._scheduler: Final = scheduler

    async def run(self, data: SendPushToUserCommand) -> None:
        await self._scheduler.schedule_send_web_push(
            user_id=data.target_user_id,
            title=data.title,
            body=data.body,
            url=data.url,
            tag=data.tag,
            icon=data.icon,
            category=data.category.value,
            bypass_preferences=False,
        )

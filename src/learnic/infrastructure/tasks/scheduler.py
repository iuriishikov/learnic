from typing import Final

from typing_extensions import override

from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.constants import (
    INVITE_TOKEN_TTL_DAYS,
)
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.tasks.handlers.auth_email import (
    send_password_reset_email_task,
    send_verification_email_task,
)
from learnic.infrastructure.tasks.handlers.collaboration_email import (
    send_collaboration_accepted_email_task,
    send_collaboration_grants_updated_email_task,
    send_collaboration_invite_email_task,
    send_collaboration_left_email_task,
    send_collaboration_revoked_email_task,
)
from learnic.infrastructure.tasks.handlers.email import send_email_task
from learnic.infrastructure.tasks.handlers.example import example_task
from learnic.infrastructure.tasks.handlers.web_push import send_web_push_task
from learnic.infrastructure.tasks.handlers.webinar_schedule import (
    materialize_webinar_schedule_task,
)

_INVITE_TTL_DAYS: Final = INVITE_TOKEN_TTL_DAYS


class TaskSchedulerTaskIQ(TaskScheduler):
    @override
    async def schedule_example(self, payload: str) -> None:
        await example_task.kiq(payload)

    @override
    async def schedule_send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> None:
        # @inject strips `sender` at runtime, but .kiq type stubs
        # still expect it; silencing is the documented workaround.
        await send_email_task.kiq(to, subject, html, text)  # type: ignore[call-overload]

    @override
    async def schedule_send_verification_email(
        self,
        to: str,
        raw_token: str,
    ) -> None:
        await send_verification_email_task.kiq(to, raw_token)  # type: ignore[call-overload]

    @override
    async def schedule_send_password_reset_email(
        self,
        to: str,
        raw_token: str,
    ) -> None:
        await send_password_reset_email_task.kiq(to, raw_token)  # type: ignore[call-overload]

    @override
    async def schedule_materialize_webinar_schedule(
        self,
        schedule_id: WebinarScheduleID,
    ) -> None:
        await materialize_webinar_schedule_task.kiq(schedule_id)  # type: ignore[call-overload]

    @override
    async def schedule_send_collaboration_invite_email(
        self,
        to: str,
        product_id: ProductID,
        collaboration_id: ProductCollaborationID,
        raw_token: str,
    ) -> None:
        await send_collaboration_invite_email_task.kiq(  # type: ignore[call-overload]
            to,
            product_id,
            collaboration_id,
            raw_token,
            _INVITE_TTL_DAYS,
        )

    @override
    async def schedule_send_collaboration_accepted_email(
        self,
        to: str,
        product_id: ProductID,
        collaborator_id: UserID,
    ) -> None:
        del collaborator_id  # signed-link/email, no per-user templating
        await send_collaboration_accepted_email_task.kiq(  # type: ignore[call-overload]
            to,
            product_id,
        )

    @override
    async def schedule_send_collaboration_revoked_email(
        self,
        to: str,
        product_id: ProductID,
    ) -> None:
        await send_collaboration_revoked_email_task.kiq(  # type: ignore[call-overload]
            to,
            product_id,
        )

    @override
    async def schedule_send_collaboration_grants_updated_email(
        self,
        to: str,
        product_id: ProductID,
    ) -> None:
        await send_collaboration_grants_updated_email_task.kiq(  # type: ignore[call-overload]
            to,
            product_id,
        )

    @override
    async def schedule_send_collaboration_left_email(
        self,
        to: str,
        product_id: ProductID,
        collaborator_id: UserID,
    ) -> None:
        del collaborator_id
        await send_collaboration_left_email_task.kiq(  # type: ignore[call-overload]
            to,
            product_id,
        )

    @override
    async def schedule_send_web_push(
        self,
        *,
        user_id: UserID,
        title: str,
        body: str,
        url: str | None = None,
        tag: str | None = None,
        icon: str | None = None,
        category: str | None = None,
        bypass_preferences: bool = False,
    ) -> None:
        await send_web_push_task.kiq(  # type: ignore[call-overload]
            user_id,
            title,
            body,
            url,
            tag,
            icon,
            category,
            bypass_preferences,
        )

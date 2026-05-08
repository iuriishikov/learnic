"""TaskIQ tasks delivering collaboration-related emails.

The application layer never builds these strings — handlers call
:class:`TaskScheduler` methods, the scheduler dispatches via the
broker, and these tasks render the email body and forward it to
the :class:`EmailService` adapter. Anonymous outline of each
template is in the helper functions.
"""

from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.common.email.components import (
    EmailButton,
    EmailComponent,
    EmailParagraph,
)
from learnic.application.common.email.service import EmailService
from learnic.infrastructure.configs import SecurityConfig
from learnic.infrastructure.tasks.broker import broker


def _invite_link(
    base_url: str,
    product_id: UUID,
    collaboration_id: UUID,
    raw_token: str,
) -> str:
    return (
        f"{base_url.rstrip('/')}"
        f"/products/{product_id}/collaboration-invitation/"
        f"{collaboration_id}/accept?token={raw_token}"
    )


def _product_link(base_url: str, product_id: UUID) -> str:
    return f"{base_url.rstrip('/')}/products/{product_id}"


def _invite_components(
    link: str,
    expires_in_days: int,
) -> list[EmailComponent]:
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            "Вас пригласили в совместную работу над продуктом на платформе Learnic.",
        ),
        EmailButton(label="Принять приглашение", url=link),
        EmailParagraph.text(
            f"Ссылка действует {expires_in_days} дней. После того как "
            "вы примете приглашение, нужные права будут выданы "
            "автоматически.",
        ),
    ]


def _accepted_components(link: str) -> list[EmailComponent]:
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            "Приглашение к совместной работе принято.",
        ),
        EmailButton(label="Открыть продукт", url=link),
    ]


def _revoked_components(link: str) -> list[EmailComponent]:
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            "Доступ к продукту был отозван. Если это произошло по "
            "ошибке — свяжитесь с автором продукта.",
        ),
        EmailButton(label="Открыть Learnic", url=link),
    ]


def _grants_updated_components(link: str) -> list[EmailComponent]:
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            "Ваши права для совместной работы над продуктом были обновлены.",
        ),
        EmailButton(label="Открыть продукт", url=link),
    ]


def _left_components(link: str) -> list[EmailComponent]:
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            "Один из коллабораторов покинул ваш продукт.",
        ),
        EmailButton(label="Открыть продукт", url=link),
    ]


@broker.task
@inject(patch_module=True)
async def send_collaboration_invite_email_task(
    to: str,
    product_id: UUID,
    collaboration_id: UUID,
    raw_token: str,
    expires_in_days: int,
    email_service: FromDishka[EmailService],
    security: FromDishka[SecurityConfig],
) -> None:
    """Deliver a collaboration-invite email."""
    link = _invite_link(
        security.frontend_base_url,
        product_id,
        collaboration_id,
        raw_token,
    )
    await email_service.send(
        to=to,
        subject="Приглашение к совместной работе на Learnic",
        components=_invite_components(link, expires_in_days),
    )


@broker.task
@inject(patch_module=True)
async def send_collaboration_accepted_email_task(
    to: str,
    product_id: UUID,
    email_service: FromDishka[EmailService],
    security: FromDishka[SecurityConfig],
) -> None:
    """Notify the inviter that the invite was accepted."""
    link = _product_link(security.frontend_base_url, product_id)
    await email_service.send(
        to=to,
        subject="Приглашение принято",
        components=_accepted_components(link),
    )


@broker.task
@inject(patch_module=True)
async def send_collaboration_revoked_email_task(
    to: str,
    product_id: UUID,
    email_service: FromDishka[EmailService],
    security: FromDishka[SecurityConfig],
) -> None:
    """Notify a collaborator that access was revoked."""
    link = _product_link(security.frontend_base_url, product_id)
    await email_service.send(
        to=to,
        subject="Доступ к продукту отозван",
        components=_revoked_components(link),
    )


@broker.task
@inject(patch_module=True)
async def send_collaboration_grants_updated_email_task(
    to: str,
    product_id: UUID,
    email_service: FromDishka[EmailService],
    security: FromDishka[SecurityConfig],
) -> None:
    """Notify a collaborator that grants changed."""
    link = _product_link(security.frontend_base_url, product_id)
    await email_service.send(
        to=to,
        subject="Изменены права совместной работы",
        components=_grants_updated_components(link),
    )


@broker.task
@inject(patch_module=True)
async def send_collaboration_left_email_task(
    to: str,
    product_id: UUID,
    email_service: FromDishka[EmailService],
    security: FromDishka[SecurityConfig],
) -> None:
    """Notify the owner that a collaborator left."""
    link = _product_link(security.frontend_base_url, product_id)
    await email_service.send(
        to=to,
        subject="Коллаборатор покинул продукт",
        components=_left_components(link),
    )

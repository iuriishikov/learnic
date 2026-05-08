from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.common.email.components import (
    EmailButton,
    EmailComponent,
    EmailParagraph,
)
from learnic.application.common.email.service import EmailService
from learnic.infrastructure.configs import SecurityConfig
from learnic.infrastructure.tasks.broker import broker


def _verify_link(base_url: str, raw_token: str) -> str:
    return f"{base_url.rstrip('/')}/verify-email?token={raw_token}"


def _reset_link(base_url: str, raw_token: str) -> str:
    return f"{base_url.rstrip('/')}/reset-password?token={raw_token}"


def _verification_components(link: str) -> list[EmailComponent]:
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            "Подтвердите ваш email, нажав на кнопку ниже:",
        ),
        EmailButton(label="Подтвердить email", url=link),
        EmailParagraph.text("Ссылка действует 24 часа."),
    ]


def _password_reset_components(link: str) -> list[EmailComponent]:
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            "Чтобы установить новый пароль, нажмите на кнопку ниже:",
        ),
        EmailButton(label="Сбросить пароль", url=link),
        EmailParagraph.text("Ссылка действует 1 час."),
    ]


@broker.task
@inject(patch_module=True)
async def send_verification_email_task(
    to: str,
    raw_token: str,
    email_service: FromDishka[EmailService],
    security: FromDishka[SecurityConfig],
) -> None:
    """Deliver the email-verification link.

    Args:
        to: Recipient email address.
        raw_token: Single-use verification token.
        email_service: Injected component-based email service.
        security: Injected security config (for frontend base URL).
    """
    link = _verify_link(security.frontend_base_url, raw_token)
    await email_service.send(
        to=to,
        subject="Подтверждение email",
        components=_verification_components(link),
    )


@broker.task
@inject(patch_module=True)
async def send_password_reset_email_task(
    to: str,
    raw_token: str,
    email_service: FromDishka[EmailService],
    security: FromDishka[SecurityConfig],
) -> None:
    """Deliver the password-reset link.

    Args:
        to: Recipient email address.
        raw_token: Single-use reset token.
        email_service: Injected component-based email service.
        security: Injected security config (for frontend base URL).
    """
    link = _reset_link(security.frontend_base_url, raw_token)
    await email_service.send(
        to=to,
        subject="Сброс пароля",
        components=_password_reset_components(link),
    )

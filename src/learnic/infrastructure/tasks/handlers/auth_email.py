from dishka.integrations.taskiq import FromDishka, inject

from learnic.application.common.email.sender import EmailSender
from learnic.infrastructure.configs import SecurityConfig
from learnic.infrastructure.tasks.broker import broker


def _verify_link(base_url: str, raw_token: str) -> str:
    return f"{base_url.rstrip('/')}/verify-email?token={raw_token}"


def _reset_link(base_url: str, raw_token: str) -> str:
    return f"{base_url.rstrip('/')}/reset-password?token={raw_token}"


@broker.task
@inject(patch_module=True)
async def send_verification_email_task(
    to: str,
    raw_token: str,
    sender: FromDishka[EmailSender],
    security: FromDishka[SecurityConfig],
) -> None:
    """Deliver the email-verification link.

    Args:
        to: Recipient email address.
        raw_token: Single-use verification token.
        sender: Injected email transport.
        security: Injected security config (for frontend base URL).
    """
    link = _verify_link(security.frontend_base_url, raw_token)
    html = (
        "<p>Подтвердите ваш email, перейдя по ссылке:</p>"
        f'<p><a href="{link}">Подтвердить email</a></p>'
        "<p>Ссылка действует 24 часа.</p>"
    )
    text = f"Подтвердите email: {link}\nСсылка действует 24 часа."
    await sender.send(to=to, subject="Подтверждение email", html=html, text=text)


@broker.task
@inject(patch_module=True)
async def send_password_reset_email_task(
    to: str,
    raw_token: str,
    sender: FromDishka[EmailSender],
    security: FromDishka[SecurityConfig],
) -> None:
    """Deliver the password-reset link.

    Args:
        to: Recipient email address.
        raw_token: Single-use reset token.
        sender: Injected email transport.
        security: Injected security config (for frontend base URL).
    """
    link = _reset_link(security.frontend_base_url, raw_token)
    html = (
        "<p>Чтобы установить новый пароль, перейдите по ссылке:</p>"
        f'<p><a href="{link}">Сбросить пароль</a></p>'
        "<p>Ссылка действует 1 час.</p>"
    )
    text = f"Сбросить пароль: {link}\nСсылка действует 1 час."
    await sender.send(to=to, subject="Сброс пароля", html=html, text=text)

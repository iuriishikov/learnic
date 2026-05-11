from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.auth.register import (
    RegisterCommand,
    RegisterCommandHandler,
)
from learnic.application.common.errors import EmailAlreadyRegisteredError
from learnic.application.common.notifications.channels import EmailPayload
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.infrastructure.configs import SecurityConfig


def _build_handler(
    *,
    transaction: AsyncMock,
    entity_saver: MagicMock,
    user_gateway: AsyncMock,
    hasher: MagicMock,
    email_tokens: AsyncMock,
    signup_sessions: AsyncMock,
    notifier: AsyncMock,
    config: SecurityConfig,
) -> RegisterCommandHandler:
    return RegisterCommandHandler(
        transaction=transaction,
        entity_saver=entity_saver,
        user_gateway=user_gateway,
        hasher=hasher,
        email_tokens=email_tokens,
        signup_sessions=signup_sessions,
        notifier=notifier,
        config=config,
    )


async def test_register_success_mints_tokens_and_notifies(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_email_tokens: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_notifier: AsyncMock,
    security_config: SecurityConfig,
) -> None:
    fake_user_gateway.with_email.return_value = None

    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        email_tokens=fake_email_tokens,
        signup_sessions=fake_signup_sessions,
        notifier=fake_notifier,
        config=security_config,
    )
    result = await handler.run(
        RegisterCommand(
            email="new@example.com",
            password="correcthorsebattery",
            first_name="Ivan",
            last_name="Ivanov",
        )
    )

    assert result.signup_session_token == "raw-signup-token"
    fake_entity_saver.add_one.assert_called_once()
    fake_email_tokens.issue.assert_awaited_once()
    fake_signup_sessions.issue.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()
    fake_notifier.send.assert_awaited_once()
    sent_kwargs = fake_notifier.send.await_args.kwargs
    assert sent_kwargs["category"] is NotificationCategory.SECURITY
    payloads = sent_kwargs["payloads"]
    assert NotificationChannel.EMAIL in payloads
    email_payload = payloads[NotificationChannel.EMAIL]
    assert isinstance(email_payload, EmailPayload)
    assert email_payload.subject == "Подтверждение email"
    assert len(email_payload.components) > 0


async def test_register_rejects_existing_email(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_email_tokens: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_notifier: AsyncMock,
    security_config: SecurityConfig,
    verified_user,
) -> None:
    fake_user_gateway.with_email.return_value = verified_user

    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        email_tokens=fake_email_tokens,
        signup_sessions=fake_signup_sessions,
        notifier=fake_notifier,
        config=security_config,
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        await handler.run(
            RegisterCommand(
                email="user@example.com",
                password="correcthorsebattery",
                first_name="Ivan",
                last_name="Ivanov",
            )
        )

    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_notifier.send.assert_not_called()

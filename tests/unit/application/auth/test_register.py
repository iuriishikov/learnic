from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.auth.register import (
    RegisterCommand,
    RegisterCommandHandler,
)
from learnic.application.common.errors import EmailAlreadyRegisteredError
from learnic.infrastructure.configs import SecurityConfig


def _build_handler(
    *,
    transaction: AsyncMock,
    entity_saver: MagicMock,
    user_gateway: AsyncMock,
    hasher: MagicMock,
    email_tokens: AsyncMock,
    signup_sessions: AsyncMock,
    task_scheduler: AsyncMock,
    config: SecurityConfig,
    anon_rate_limiter: AsyncMock,
) -> RegisterCommandHandler:
    return RegisterCommandHandler(
        transaction=transaction,
        entity_saver=entity_saver,
        user_gateway=user_gateway,
        hasher=hasher,
        email_tokens=email_tokens,
        signup_sessions=signup_sessions,
        task_scheduler=task_scheduler,
        config=config,
        anon_rate_limiter=anon_rate_limiter,
    )


async def test_register_success_mints_tokens_and_schedules_email(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_email_tokens: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_scheduler: AsyncMock,
    security_config: SecurityConfig,
    fake_anon_rate_limiter: AsyncMock,
) -> None:
    fake_user_gateway.with_email.return_value = None

    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        email_tokens=fake_email_tokens,
        signup_sessions=fake_signup_sessions,
        task_scheduler=fake_scheduler,
        config=security_config,
        anon_rate_limiter=fake_anon_rate_limiter,
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
    fake_scheduler.schedule_send_email.assert_awaited_once()
    sent_kwargs = fake_scheduler.schedule_send_email.await_args.kwargs
    assert sent_kwargs["to"] == "new@example.com"
    assert sent_kwargs["subject"] == "Подтверждение email"
    assert len(sent_kwargs["components"]) > 0


async def test_register_rejects_existing_unreclaimable_email(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_email_tokens: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_scheduler: AsyncMock,
    security_config: SecurityConfig,
    fake_anon_rate_limiter: AsyncMock,
    verified_user,
) -> None:
    fake_user_gateway.with_email.return_value = verified_user
    # Verified holder — the on-demand reclaim finds no abandoned row and
    # returns False, so registration is still rejected.
    fake_user_gateway.delete_abandoned_unverified_by_email.return_value = (
        False
    )

    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        email_tokens=fake_email_tokens,
        signup_sessions=fake_signup_sessions,
        task_scheduler=fake_scheduler,
        config=security_config,
        anon_rate_limiter=fake_anon_rate_limiter,
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

    # The reclaim was attempted (and declined) before rejecting.
    reclaim_call = fake_user_gateway.delete_abandoned_unverified_by_email
    reclaim_call.assert_awaited_once()
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_scheduler.schedule_send_email.assert_not_called()


async def test_register_reclaims_abandoned_unverified_email(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    fake_hasher: MagicMock,
    fake_email_tokens: AsyncMock,
    fake_signup_sessions: AsyncMock,
    fake_scheduler: AsyncMock,
    security_config: SecurityConfig,
    fake_anon_rate_limiter: AsyncMock,
    unverified_user,
) -> None:
    # The address is held by an abandoned, unverified registration past
    # self-recovery: the gateway deletes it on demand (returns True) and
    # the new registration proceeds over the freed email.
    fake_user_gateway.with_email.return_value = unverified_user
    fake_user_gateway.delete_abandoned_unverified_by_email.return_value = True

    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
        hasher=fake_hasher,
        email_tokens=fake_email_tokens,
        signup_sessions=fake_signup_sessions,
        task_scheduler=fake_scheduler,
        config=security_config,
        anon_rate_limiter=fake_anon_rate_limiter,
    )

    result = await handler.run(
        RegisterCommand(
            email="user@example.com",
            password="correcthorsebattery",
            first_name="Ivan",
            last_name="Ivanov",
        )
    )

    assert result.signup_session_token == "raw-signup-token"
    reclaim_call = fake_user_gateway.delete_abandoned_unverified_by_email
    reclaim_call.assert_awaited_once()
    fake_entity_saver.add_one.assert_called_once()
    fake_transaction.commit.assert_awaited_once()
    fake_scheduler.schedule_send_email.assert_awaited_once()

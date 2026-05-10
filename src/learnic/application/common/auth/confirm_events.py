from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from learnic.entities.user.models import UserID


class ConfirmEventKind(StrEnum):
    """Discriminator for the per-user confirm-events channel.

    ``CONFIRMED`` fires after a single-token email confirmation
    (``EmailTokenPurpose``) has been consumed and committed. The
    initiator tab subscribes to react in real time — finalize signup,
    refresh a profile field, redirect, etc.
    """

    CONFIRMED = "confirmed"


@dataclass(slots=True, frozen=True)
class ConfirmEvent:
    """Push payload delivered via ``WS /users/me/confirm-events``.

    ``user_id`` is the channel key. ``purpose`` mirrors
    :class:`EmailTokenPurpose` values so subscribers can filter on
    the action they're waiting for.
    """

    user_id: UserID
    kind: ConfirmEventKind
    purpose: str


class ConfirmEventBus(Protocol):
    """Per-user pub/sub channel for email-confirmation deltas.

    Channel keyed by ``user_id`` so initiator tabs (registration,
    profile, danger-zone, etc.) get push notifications without long
    polling. Producers publish strictly **after** the request
    transaction commits — subscribers must never observe rolled-back
    confirmations.
    """

    async def publish(self, event: ConfirmEvent) -> None: ...

    def subscribe(self, user_id: UserID) -> AsyncIterator[ConfirmEvent]: ...

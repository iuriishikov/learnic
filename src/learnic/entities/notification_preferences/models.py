from dataclasses import dataclass, field
from typing import Final

from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.user.models import UserID


def _all_categories_default(value: bool) -> dict[NotificationCategory, bool]:
    return {category: value for category in NotificationCategory}


# Email is opt-in per category by default — digest-style mail must not surprise
# users — EXCEPT account-safety / transactional categories, which must always be
# able to reach the inbox. Without this, a user who has never opened the
# settings page (no stored preferences row) silently never receives security
# mail: defaults_for() would set every category False and is_enabled() would
# gate EMAIL off (exactly how the new-login / verification mail went missing).
_EMAIL_ON_BY_DEFAULT: Final[frozenset[NotificationCategory]] = frozenset(
    {NotificationCategory.SECURITY},
)


def _email_category_defaults() -> dict[NotificationCategory, bool]:
    return {
        category: category in _EMAIL_ON_BY_DEFAULT
        for category in NotificationCategory
    }


@dataclass
class NotificationPreferences:
    """Per-user matrix of channel × category opt-in flags.

    One row per user; missing rows are treated as "all defaults"
    (push on; email off except account-safety ``SECURITY``, which is
    on; in-app on) — the reader materialises a
    default object so callers never have to special-case the
    first-time path. ``IN_APP`` is always ``True`` regardless of
    storage; the publisher must not gate the in-app fanout on this
    matrix to keep the bell badge truthful.
    """

    user_id: UserID
    push: dict[NotificationCategory, bool] = field(
        default_factory=lambda: _all_categories_default(True),
    )
    email: dict[NotificationCategory, bool] = field(
        default_factory=_email_category_defaults,
    )

    @classmethod
    def defaults_for(cls, user_id: UserID) -> "NotificationPreferences":
        """Return the implicit defaults for a user without a stored row.

        Push: opted in for every category — most common expectation
        after the user clicked "Enable notifications". Email: opted
        out by default to avoid surprising legacy users with digest
        mail, EXCEPT account-safety/transactional categories
        (``SECURITY``), which default ON so security mail (new-login
        alert, etc.) always reaches a user who has never touched the
        settings page. The settings page still lets users flip
        individual categories.
        """
        return cls(
            user_id=user_id,
            push=_all_categories_default(True),
            email=_email_category_defaults(),
        )

    def is_enabled(
        self,
        channel: NotificationChannel,
        category: NotificationCategory,
    ) -> bool:
        if channel is NotificationChannel.IN_APP:
            return True
        if channel is NotificationChannel.PUSH:
            return self.push.get(category, True)
        return self.email.get(category, False)

    def set_channel(
        self,
        channel: NotificationChannel,
        category: NotificationCategory,
        enabled: bool,
    ) -> None:
        """Update one cell of the matrix; ``IN_APP`` writes are no-ops."""
        if channel is NotificationChannel.IN_APP:
            return
        if channel is NotificationChannel.PUSH:
            self.push[category] = enabled
            return
        self.email[category] = enabled

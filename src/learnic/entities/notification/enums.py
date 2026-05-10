from enum import StrEnum


class NotificationKind(StrEnum):
    """Discriminator for the polymorphic notification body.

    Each kind maps to exactly one subtype table in
    :mod:`learnic.infrastructure.persistence.models.notification`.
    Adding a new kind requires a new ``notification_<kind>`` table
    and a matching ``NotificationDetails`` subclass — option B
    persistence as agreed in the design discussion.
    """

    INVITE_SENT = "invite_sent"
    INVITE_ACCEPTED = "invite_accepted"
    INVITE_DECLINED = "invite_declined"
    ACCESS_REVOKED = "access_revoked"


class NotificationCategory(StrEnum):
    """Tab grouping in the notifications panel.

    Mirrors the segmented control in the panel mock-ups —
    ``View all`` aggregates every category, ``Invites`` is the
    invite tab, ``Files`` and ``Jobs`` are reserved for future
    notification kinds. ``OTHER`` catches anything that does not
    fit a dedicated tab so the panel never shows an empty bucket.
    """

    INVITES = "invites"
    FILES = "files"
    JOBS = "jobs"
    OTHER = "other"


class NotificationChannel(StrEnum):
    """Delivery channels controlled by user notification preferences.

    ``IN_APP`` is the always-on bell-icon panel — user preferences
    cannot disable it (``in-app`` toggle in the settings UI is
    rendered as locked-on). ``PUSH`` and ``EMAIL`` are opt-in per
    category and respected at the publisher boundary.
    """

    PUSH = "push"
    EMAIL = "email"
    IN_APP = "in_app"

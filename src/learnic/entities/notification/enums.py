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
    NEW_LOGIN = "new_login"
    STORAGE_QUOTA_WARNING = "storage_quota_warning"
    STORAGE_QUOTA_ENFORCED = "storage_quota_enforced"


class NotificationCategory(StrEnum):
    """Tab grouping in the notifications panel.

    Mirrors the segmented control in the panel mock-ups —
    ``View all`` aggregates every category. ``Teaching`` covers
    everything an author or collaborator does on the teaching side
    (invites, access changes, future content events). ``Learning``
    is the student-side counterpart — events that surface to a
    learner (course progress, deadlines, instructor messages,
    future content events on courses they are enrolled in).
    ``Security`` covers account-safety events (new login, password
    changed, suspicious activity) so the user sees them in a
    dedicated tab. ``Files`` and ``Jobs`` are reserved for future
    notification kinds. ``OTHER`` catches anything that does not
    fit a dedicated tab so the panel never shows an empty bucket.
    """

    TEACHING = "teaching"
    LEARNING = "learning"
    SECURITY = "security"
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

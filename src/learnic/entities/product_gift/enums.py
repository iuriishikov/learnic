from enum import StrEnum


class GiftStatus(StrEnum):
    """Lifecycle state of a :class:`ProductGift`.

    ``PENDING_INVITE`` covers both invite types:

    - by-email invites where the recipient is not yet a registered
      user (``recipient_id`` is ``None`` until accept),
    - by-user-id invites where the recipient already has an account
      but has not accepted yet.

    ``ACCEPTED`` means the recipient took the gift; the enrollment is
    created at that moment and the row is kept for audit. ``DECLINED``
    is set when the recipient explicitly rejects the gift — terminal,
    preserved so the gifter can see the outcome. ``REVOKED`` is
    terminal — the gifter cancelled a still-pending gift; only a
    pending gift can be revoked (an accepted gift already produced an
    enrollment and is not undone here).
    """

    PENDING_INVITE = "pending_invite"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"

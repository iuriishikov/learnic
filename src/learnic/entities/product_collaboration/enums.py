from enum import StrEnum


class CollaborationStatus(StrEnum):
    """Lifecycle state of a :class:`ProductCollaboration`.

    ``PENDING_INVITE`` covers both invite types:

    - by-email invites where the invitee is not yet a registered
      user (``collaborator_id`` is ``None`` until accept),
    - by-user-id invites where the invitee already has an account
      but has not clicked the accept link yet.

    ``ACTIVE`` means the invitee has accepted; only then are
    grants effective. ``REVOKED`` is terminal — the collaboration
    is preserved for audit and the row is never reactivated.
    """

    PENDING_INVITE = "pending_invite"
    ACTIVE = "active"
    REVOKED = "revoked"

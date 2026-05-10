from enum import StrEnum


class CollaborationStatus(StrEnum):
    """Lifecycle state of a :class:`ProductCollaboration`.

    ``PENDING_INVITE`` covers both invite types:

    - by-email invites where the invitee is not yet a registered
      user (``collaborator_id`` is ``None`` until accept),
    - by-user-id invites where the invitee already has an account
      but has not clicked the accept link yet.

    ``ACTIVE`` means the invitee has accepted; only then are
    grants effective. ``DECLINED`` is set when the recipient
    explicitly rejects the in-app invite — terminal, the row is
    preserved for audit so the inviter can see the outcome.
    ``REVOKED`` is terminal — manager-initiated end of the
    collaboration; the row is preserved for audit and never
    reactivated.
    """

    PENDING_INVITE = "pending_invite"
    ACTIVE = "active"
    DECLINED = "declined"
    REVOKED = "revoked"

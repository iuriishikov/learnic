"""Shared read-side user projection embedded in other resources.

Every endpoint that exposes a user *as a reference* inside a parent
resource (product author, collaboration collaborator, notification
actor, …) returns the same shape. ``UserRefView`` is that shape on
the application side; ``UserRefSchema`` mirrors it at the HTTP
boundary. Keep them in lock-step — adding a field here means adding
it to the schema and to every reader join that hydrates one.

Not used by the full-profile endpoint (``GET /users/{id}``) — that
returns ``UserSchema`` with avatar, cover, and description on top —
nor by name-search hits, which intentionally omit ``email`` to
prevent address enumeration.
"""

from dataclasses import dataclass

from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UserRefView:
    """Read-side projection of a user embedded in a parent resource.

    Carries the raw name parts (so the schema layer can collapse them
    via ``build_full_name``) and the raw email (so the schema layer
    can mask it via ``mask_email``). Domain rules are not enforced
    here — these are projections, not entities.
    """

    oid: UserID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


class CursorsEventKind(StrEnum):
    """Wire-level discriminator for ``CursorsEvent``.

    The set is closed and small; consumers must handle every
    variant. Values are also what is emitted as ``type`` on the
    WebSocket envelope (the wire layer is structurally identical
    to the in-process bus message).
    """

    CURSOR_AT = "cursor_at"
    CURSOR_LEFT = "cursor_left"
    USER_GONE = "user_gone"


@dataclass(slots=True, frozen=True)
class CursorsEvent:
    """One delta on a product's live cursor stream.

    Published by the WS receive loop after it accepts a client
    message, fans out across replicas via Redis pub/sub, and is
    forwarded to every subscribed client whose ``user_id`` does
    not match ``user_id`` (the originator never sees their own
    deltas).

    ``field_id`` is set for ``CURSOR_AT`` and ``CURSOR_LEFT``;
    ``None`` for ``USER_GONE``. ``action`` is set for ``CURSOR_AT``
    only.
    """

    kind: CursorsEventKind
    product_id: ProductID
    user_id: UserID
    field_id: str | None
    action: str | None
    occurred_at: datetime

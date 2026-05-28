import hashlib
import secrets

from learnic.entities.common.value_object import ValueObject
from learnic.entities.product_gift.constants import (
    INVITE_TOKEN_BYTES,
    INVITE_TOKEN_HASH_LEN,
    INVITE_TOKEN_MAX_LEN,
)
from learnic.entities.product_gift.errors import InvalidInviteTokenError


class InviteToken(ValueObject):
    """Opaque acceptance token for a pending gift.

    The plaintext token only travels in gift emails and accept
    requests; the database stores its sha256 hex digest via
    :class:`InviteTokenHash`. The split keeps a leaked DB dump from
    being usable to accept gifts and lets the accept-handler do a
    constant-time comparison against a deterministically-computed
    hash.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidInviteTokenError
        if len(self.value) > INVITE_TOKEN_MAX_LEN:
            raise InvalidInviteTokenError

    @classmethod
    def generate(cls) -> "InviteToken":
        return cls(secrets.token_urlsafe(INVITE_TOKEN_BYTES))

    def hashed(self) -> "InviteTokenHash":
        digest = hashlib.sha256(self.value.encode("utf-8")).hexdigest()
        return InviteTokenHash(digest)


class InviteTokenHash(ValueObject):
    """sha256 hex digest of an :class:`InviteToken`.

    Stored in the ``invite_token_hash`` column. Compared against a
    fresh hash of the user-supplied token in
    ``ProductGift.accept(...)``.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) != INVITE_TOKEN_HASH_LEN:
            raise InvalidInviteTokenError

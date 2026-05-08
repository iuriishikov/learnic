import pytest

from learnic.entities.product_collaboration.constants import (
    INVITE_TOKEN_HASH_LEN,
    INVITE_TOKEN_MAX_LEN,
)
from learnic.entities.product_collaboration.errors import (
    InvalidInviteTokenError,
)
from learnic.entities.product_collaboration.value_objects import (
    InviteToken,
    InviteTokenHash,
)


class TestInviteToken:
    def test_generate_produces_token(self) -> None:
        token = InviteToken.generate()
        assert token.value
        assert len(token.value) <= INVITE_TOKEN_MAX_LEN

    def test_rejects_empty(self) -> None:
        with pytest.raises(InvalidInviteTokenError):
            InviteToken("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(InvalidInviteTokenError):
            InviteToken("x" * (INVITE_TOKEN_MAX_LEN + 1))

    def test_hashed_returns_sha256_hex(self) -> None:
        token = InviteToken("a" * 32)
        digest = token.hashed()
        assert isinstance(digest, InviteTokenHash)
        assert len(digest.value) == INVITE_TOKEN_HASH_LEN

    def test_two_hashes_match_for_same_token(self) -> None:
        token = InviteToken("plain-token-value")
        assert token.hashed() == token.hashed()

    def test_hashes_differ_for_different_tokens(self) -> None:
        a = InviteToken("a" * 32)
        b = InviteToken("b" * 32)
        assert a.hashed() != b.hashed()


class TestInviteTokenHash:
    def test_rejects_wrong_length(self) -> None:
        with pytest.raises(InvalidInviteTokenError):
            InviteTokenHash("short")

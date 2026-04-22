import hashlib
import secrets

_TOKEN_BYTES = 32


def generate_raw_token() -> str:
    """Return a URL-safe random token with ~256 bits of entropy."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_token(raw: str) -> bytes:
    """SHA-256 digest of ``raw``; what we store server-side."""
    return hashlib.sha256(raw.encode("utf-8")).digest()

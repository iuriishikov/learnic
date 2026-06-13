from typing import Protocol

from learnic.entities.user.value_objects import PasswordHash, RawPassword


class PasswordHasher(Protocol):
    """Hashing and verification of user passwords.

    Implementations are free to pick the KDF (argon2id, bcrypt, ...);
    application handlers only depend on this interface.
    """

    async def hash(self, raw: RawPassword) -> PasswordHash:
        """Return the encoded hash of ``raw``.

        Awaitable so the memory-hard KDF runs off the event loop (the
        adapter offloads it to a worker thread).
        """
        ...

    async def verify(self, raw: RawPassword, stored: PasswordHash) -> bool:
        """Return ``True`` if ``raw`` matches ``stored``.

        Returns ``False`` on mismatch rather than raising; implementations
        should not leak timing differences between unknown-user and
        wrong-password paths. Awaitable so the KDF runs off the event loop.
        """
        ...

    async def verify_dummy(self, raw: RawPassword) -> None:
        """Verify ``raw`` against a fixed decoy hash and discard the result.

        Callers use this on the unknown-user branch of login so that the
        response latency matches the existing-user (real ``verify``) path,
        preventing timing-based account enumeration. Awaitable so the decoy
        KDF runs off the event loop, exactly like ``verify``.
        """
        ...

    def needs_rehash(self, stored: PasswordHash) -> bool:
        """Return ``True`` if ``stored`` should be upgraded.

        Used to transparently upgrade hashes when KDF parameters change.
        """
        ...

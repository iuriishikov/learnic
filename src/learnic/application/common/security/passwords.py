from typing import Protocol

from learnic.entities.user.value_objects import PasswordHash, RawPassword


class PasswordHasher(Protocol):
    """Hashing and verification of user passwords.

    Implementations are free to pick the KDF (argon2id, bcrypt, ...);
    application handlers only depend on this interface.
    """

    def hash(self, raw: RawPassword) -> PasswordHash:
        """Return the encoded hash of ``raw``."""
        ...

    def verify(self, raw: RawPassword, stored: PasswordHash) -> bool:
        """Return ``True`` if ``raw`` matches ``stored``.

        Returns ``False`` on mismatch rather than raising; implementations
        should not leak timing differences between unknown-user and
        wrong-password paths.
        """
        ...

    def needs_rehash(self, stored: PasswordHash) -> bool:
        """Return ``True`` if ``stored`` should be upgraded.

        Used to transparently upgrade hashes when KDF parameters change.
        """
        ...

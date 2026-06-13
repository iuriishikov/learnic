import asyncio
from typing import Final

from argon2 import PasswordHasher as _Argon2
from argon2 import exceptions as _argon2_exc
from typing_extensions import override

from learnic.application.common.security.passwords import PasswordHasher
from learnic.entities.user.value_objects import PasswordHash, RawPassword

# Fixed plaintext used to derive the decoy hash for ``verify_dummy``.
# Its only job is to give the unknown-user login branch a real KDF to
# run so its latency matches the existing-user path; it never matches a
# user-supplied password.
_DECOY_PLAINTEXT: Final = "decoy-password-for-constant-time-login"


class Argon2PasswordHasher(PasswordHasher):
    """``PasswordHasher`` implemented on top of ``argon2-cffi``.

    Argon2id is a memory-hard KDF costing tens of milliseconds of pure
    CPU per call, so every ``hash``/``verify`` is offloaded to a worker
    thread via ``asyncio.to_thread`` to keep the event loop responsive.
    """

    def __init__(self) -> None:
        self._ph: Final = _Argon2()
        # Precompute a real Argon2 hash once at startup so ``verify_dummy``
        # exercises the full KDF (a non-Argon2 string would raise
        # ``InvalidHashError`` immediately and defeat the timing equalization).
        self._decoy_hash: Final = PasswordHash(self._ph.hash(_DECOY_PLAINTEXT))

    @override
    async def hash(self, raw: RawPassword) -> PasswordHash:
        return await asyncio.to_thread(self._hash_sync, raw)

    @override
    async def verify(self, raw: RawPassword, stored: PasswordHash) -> bool:
        return await asyncio.to_thread(self._verify_sync, raw, stored)

    @override
    async def verify_dummy(self, raw: RawPassword) -> None:
        await asyncio.to_thread(self._verify_sync, raw, self._decoy_hash)

    @override
    def needs_rehash(self, stored: PasswordHash) -> bool:
        return bool(self._ph.check_needs_rehash(stored.value))

    def _hash_sync(self, raw: RawPassword) -> PasswordHash:
        return PasswordHash(self._ph.hash(raw.value))

    def _verify_sync(self, raw: RawPassword, stored: PasswordHash) -> bool:
        try:
            return bool(self._ph.verify(stored.value, raw.value))
        except (
            _argon2_exc.VerifyMismatchError,
            _argon2_exc.InvalidHashError,
            _argon2_exc.VerificationError,
        ):
            return False

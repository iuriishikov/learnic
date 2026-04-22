from typing import Final

from argon2 import PasswordHasher as _Argon2
from argon2 import exceptions as _argon2_exc
from typing_extensions import override

from learnic.application.common.security.passwords import PasswordHasher
from learnic.entities.user.value_objects import PasswordHash, RawPassword


class Argon2PasswordHasher(PasswordHasher):
    """``PasswordHasher`` implemented on top of ``argon2-cffi``."""

    def __init__(self) -> None:
        self._ph: Final = _Argon2()

    @override
    def hash(self, raw: RawPassword) -> PasswordHash:
        return PasswordHash(self._ph.hash(raw.value))

    @override
    def verify(self, raw: RawPassword, stored: PasswordHash) -> bool:
        try:
            return bool(self._ph.verify(stored.value, raw.value))
        except (
            _argon2_exc.VerifyMismatchError,
            _argon2_exc.InvalidHashError,
            _argon2_exc.VerificationError,
        ):
            return False

    @override
    def needs_rehash(self, stored: PasswordHash) -> bool:
        return bool(self._ph.check_needs_rehash(stored.value))

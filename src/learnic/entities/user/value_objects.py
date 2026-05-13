from dataclasses import dataclass

from learnic.entities.common.value_object import ValueObject
from learnic.entities.user.constants import (
    DESCRIPTION_MAX_LEN,
    EMAIL_MAX_LEN,
    FIRST_NAME_MAX_LEN,
    LAST_NAME_MAX_LEN,
    PASSWORD_MAX_LEN,
    PASSWORD_MIN_LEN,
    PATRONYMIC_MAX_LEN,
    PORTFOLIO_URL_MAX_LEN,
    PUBLIC_EMAIL_MAX_LEN,
    SOCIAL_LINK_URL_MAX_LEN,
    WEBSITE_URL_MAX_LEN,
)
from learnic.entities.user.enums import SocialLinkKind
from learnic.entities.user.errors import (
    EmptyNameError,
    InvalidContactUrlError,
    InvalidDescriptionError,
    InvalidEmailError,
    InvalidPublicEmailError,
    InvalidSocialLinkUrlError,
    NameTooLongError,
    WeakPasswordError,
)


class Email(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value or len(self.value) > EMAIL_MAX_LEN:
            raise InvalidEmailError


class FirstName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNameError("first_name")
        if len(self.value) > FIRST_NAME_MAX_LEN:
            raise NameTooLongError("first_name", FIRST_NAME_MAX_LEN)


class LastName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNameError("last_name")
        if len(self.value) > LAST_NAME_MAX_LEN:
            raise NameTooLongError("last_name", LAST_NAME_MAX_LEN)


class Patronymic(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNameError("patronymic")
        if len(self.value) > PATRONYMIC_MAX_LEN:
            raise NameTooLongError("patronymic", PATRONYMIC_MAX_LEN)


class RawPassword(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if len(self.value) < PASSWORD_MIN_LEN:
            raise WeakPasswordError("too_short")
        if len(self.value) > PASSWORD_MAX_LEN:
            raise WeakPasswordError("too_long")


class PasswordHash(ValueObject):
    value: str


def _validate_http_url(value: str, max_len: int) -> str:
    """Return ``"empty" | "too_long" | "invalid_scheme"`` if invalid.

    Returned reason maps onto the ``FieldError`` subclass each VO raises.
    Empty string return means the value is acceptable.
    """
    if not value.strip():
        return "empty"
    if len(value) > max_len:
        return "too_long"
    if not (value.startswith("https://") or value.startswith("http://")):
        return "invalid_scheme"
    return ""


class WebsiteUrl(ValueObject):
    """Personal website URL exposed on the public profile."""

    value: str

    def __post_init__(self) -> None:
        reason = _validate_http_url(self.value, WEBSITE_URL_MAX_LEN)
        if reason:
            raise InvalidContactUrlError("website", reason)


class PortfolioUrl(ValueObject):
    """Portfolio URL exposed on the public profile."""

    value: str

    def __post_init__(self) -> None:
        reason = _validate_http_url(self.value, PORTFOLIO_URL_MAX_LEN)
        if reason:
            raise InvalidContactUrlError("portfolio", reason)


class PublicEmail(ValueObject):
    """Display-only contact email distinct from the login :class:`Email`.

    Validates with the same minimal "contains ``@``" + length cap rule
    as :class:`Email`; kept as a separate VO so the type system makes
    "which email did you mean" explicit at every call site.
    """

    value: str

    def __post_init__(self) -> None:
        if "@" not in self.value or len(self.value) > PUBLIC_EMAIL_MAX_LEN:
            raise InvalidPublicEmailError


class SocialLinkUrl(ValueObject):
    """URL part of a :class:`SocialLink`."""

    value: str

    def __post_init__(self) -> None:
        reason = _validate_http_url(self.value, SOCIAL_LINK_URL_MAX_LEN)
        if reason:
            raise InvalidSocialLinkUrlError(reason)


@dataclass(slots=True, frozen=True, eq=True, unsafe_hash=True)
class SocialLink:
    """A single ``(kind, url)`` pair on a user's public profile."""

    kind: SocialLinkKind
    url: SocialLinkUrl


class UserDescription(ValueObject):
    """Profile description — already-sanitized HTML.

    The VO enforces only length/emptiness invariants; HTML sanitization
    happens in the command handler via the ``HtmlSanitizer`` Protocol
    before the VO is constructed. To clear the description, set the
    user's ``description`` to ``None`` rather than constructing an
    empty VO.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidDescriptionError(DESCRIPTION_MAX_LEN)
        if len(self.value) > DESCRIPTION_MAX_LEN:
            raise InvalidDescriptionError(DESCRIPTION_MAX_LEN)

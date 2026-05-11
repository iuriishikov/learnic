from learnic.entities.common.value_object import ValueObject
from learnic.entities.user_experience.constants import (
    DESCRIPTION_MAX_LEN,
    SOURCE_URL_MAX_LEN,
    TITLE_MAX_LEN,
)
from learnic.entities.user_experience.errors import (
    EmptyUserExperienceFieldError,
    InvalidExperienceSourceUrlError,
    UserExperienceFieldTooLongError,
)


class ExperienceTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyUserExperienceFieldError("title")
        if len(self.value) > TITLE_MAX_LEN:
            raise UserExperienceFieldTooLongError("title", TITLE_MAX_LEN)


class ExperienceDescription(ValueObject):
    """Free-form description for an experience entry.

    The VO enforces only length / emptiness invariants; whatever
    sanitization the SPA-supplied text needs (e.g. HTML stripping)
    happens upstream of the VO. To clear the field, store ``None``
    on the entity rather than constructing an empty VO.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise EmptyUserExperienceFieldError("description")
        if len(self.value) > DESCRIPTION_MAX_LEN:
            raise UserExperienceFieldTooLongError(
                "description",
                DESCRIPTION_MAX_LEN,
            )


class ExperienceSourceUrl(ValueObject):
    """Optional external link associated with the experience.

    Mirrors :class:`StreamUrl` in the product aggregate — must be a
    non-empty ``http(s)://`` URL within the configured length cap.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise InvalidExperienceSourceUrlError("empty")
        if len(self.value) > SOURCE_URL_MAX_LEN:
            raise InvalidExperienceSourceUrlError("too_long")
        if not (self.value.startswith("https://") or self.value.startswith("http://")):
            raise InvalidExperienceSourceUrlError("invalid_scheme")

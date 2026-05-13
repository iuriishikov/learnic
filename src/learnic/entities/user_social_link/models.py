import uuid
from dataclasses import dataclass
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.user.enums import SocialLinkKind
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import SocialLinkUrl
from learnic.entities.user_social_link.ids import UserSocialLinkID


@dataclass
class UserSocialLink(BaseEntity[UserSocialLinkID]):
    """A single ``(kind, url)`` social-network row attached to a user.

    Owned by a :class:`User` (CASCADE on parent delete). The set is
    edited as a whole through a single PUT-list endpoint — there are
    no per-row update / delete handlers; the command handler
    rewrites the rows on every save so the table never drifts from the
    SPA's edited list. ``position`` is server-assigned from the order
    of the supplied list and is what powers the public profile's
    rendering order.
    """

    user_id: UserID
    kind: SocialLinkKind
    url: SocialLinkUrl
    position: int

    @classmethod
    def create(
        cls,
        user_id: UserID,
        kind: SocialLinkKind,
        url: SocialLinkUrl,
        position: int,
    ) -> Self:
        return cls(
            oid=UserSocialLinkID(uuid.uuid4()),
            user_id=user_id,
            kind=kind,
            url=url,
            position=position,
        )

"""Shared addressee check for the accept / decline gift handlers.

A gift is resolved by its addressee only: for by-user gifts the
actor must equal ``recipient_id``; for by-email gifts the actor's
account email must match ``invited_email``. The check guards against
a signed-in user resolving a gift addressed to someone else by
guessing the gift id.
"""

from learnic.application.common.errors import (
    InviteEmailMismatchError,
    NotResourceOwnerError,
)
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.user.models import User, UserID


def ensure_addressee(gift: ProductGift, actor: User, actor_id: UserID) -> None:
    if gift.recipient_id is not None:
        if gift.recipient_id != actor_id:
            raise NotResourceOwnerError(gift.oid, actor_id)
    elif gift.invited_email is None or gift.invited_email != actor.email:
        raise InviteEmailMismatchError

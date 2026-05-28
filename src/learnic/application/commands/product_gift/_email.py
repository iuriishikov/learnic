"""Shared helper to build the gift invitation email body.

Both invite paths (by-user, by-email) send the same two-button
email — Accept / Decline — pointing at the SPA landing routes
``/gifts/{id}/accept`` and ``/gifts/{id}/decline``, which carry the
plaintext token and call the backend accept/decline endpoints.
Keeping the copy in one place avoids drift between the two handlers.
"""

from collections.abc import Sequence

from learnic.application.common.email.components import (
    EmailButton,
    EmailComponent,
    EmailParagraph,
)
from learnic.entities.product_gift.constants import GIFT_INVITE_TTL_DAYS
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.value_objects import InviteToken

GIFT_EMAIL_SUBJECT = "Вам подарили курс на Learnic"


def build_gift_email_components(
    *,
    frontend_base_url: str,
    gift_id: ProductGiftID,
    token: InviteToken,
    product_name: str,
) -> Sequence[EmailComponent]:
    base = frontend_base_url.rstrip("/")
    accept_link = f"{base}/gifts/{gift_id}/accept?token={token.value}"
    decline_link = f"{base}/gifts/{gift_id}/decline?token={token.value}"
    return [
        EmailParagraph.text("Здравствуйте!"),
        EmailParagraph.text(
            f"Вам подарили доступ к курсу «{product_name}» на платформе "
            "Learnic. Примите подарок, чтобы получить доступ, или "
            "отклоните его.",
        ),
        EmailButton(label="Принять подарок", url=accept_link),
        EmailButton(label="Отклонить", url=decline_link),
        EmailParagraph.text(
            f"Ссылки действуют {GIFT_INVITE_TTL_DAYS} дней. После того "
            "как вы примете подарок, доступ к курсу откроется "
            "автоматически.",
        ),
    ]

"""Async ``PushSender`` backed by the ``webpush`` library and ``httpx``.

Web Push splits into two halves: per-message payload encryption
(RFC 8291, ``aes128gcm``) plus VAPID request signing, and the HTTP
POST to the browser vendor's push service. The crypto is CPU-bound
and cheap, so it runs inline on the event loop; only the POST is
I/O and it goes through a shared ``httpx.AsyncClient``. No thread
pool is involved — concurrent deliveries fan out as real coroutines,
and the client carries an explicit timeout so a stalled push service
cannot pin a caller indefinitely.

A missing or unparseable ``WEBPUSH_VAPID_PRIVATE_KEY`` (e.g. a dev
machine that has not generated keys yet) flips ``send`` into a
logged no-op so the rest of the system stays functional; production
pastes a PEM-encoded private key into the env to enable real
delivery. The matching public key is derived from that private key
rather than read from config, so the VAPID identity has a single
source of truth.
"""

import json
import logging
from dataclasses import dataclass
from typing import Final, NewType

import httpx
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)
from typing_extensions import override
from webpush import WebPush, WebPushSubscription

from learnic.application.common.push.payload import PushPayload
from learnic.application.common.push.sender import (
    PushDeliveryResult,
    PushSender,
)
from learnic.entities.push_subscription.models import PushSubscription
from learnic.infrastructure.configs import WebPushConfig
from learnic.infrastructure.push.vapid import load_vapid_private_key

_logger = logging.getLogger(__name__)

_GONE_STATUSES: Final = frozenset({404, 410})
_TTL_SECONDS: Final = 60 * 60 * 24

# DI marker: keeps the push client a distinct binding from the
# email sender's ``httpx.AsyncClient`` (dishka resolves by type).
PushHttpClient = NewType("PushHttpClient", httpx.AsyncClient)


@dataclass(slots=True, frozen=True)
class _PushDeliveryResult:
    is_gone: bool
    status_code: int | None


class WebPushSender(PushSender):
    """httpx-backed Web Push transport; no-op when VAPID is absent."""

    def __init__(
        self,
        config: WebPushConfig,
        client: PushHttpClient,
    ) -> None:
        self._client: Final = client
        self._webpush: Final = self._build(config)

    def _build(self, config: WebPushConfig) -> WebPush | None:
        key = load_vapid_private_key(config.vapid_private_key)
        if key is None:
            return None
        try:
            public_pem = key.public_key().public_bytes(
                Encoding.PEM,
                PublicFormat.SubjectPublicKeyInfo,
            )
            # ``webpush`` prepends ``mailto:`` itself, so we hand it the
            # bare address from ``WEBPUSH_VAPID_SUBJECT``.
            return WebPush(
                private_key=config.vapid_private_key.strip().encode("ascii"),
                public_key=public_pem,
                subscriber=config.vapid_subject.removeprefix("mailto:"),
                ttl=_TTL_SECONDS,
            )
        except Exception:
            _logger.exception("Failed to init Web Push; pushes disabled.")
            return None

    @override
    async def send(
        self,
        subscription: PushSubscription,
        payload: PushPayload,
    ) -> PushDeliveryResult:
        if self._webpush is None:
            _logger.debug("Web Push send skipped: VAPID is not configured")
            return _PushDeliveryResult(is_gone=False, status_code=None)
        try:
            message = self._webpush.get(
                message=json.dumps(
                    {
                        "title": payload.title,
                        "body": payload.body,
                        "url": payload.url,
                        "tag": payload.tag,
                        "icon": payload.icon,
                    },
                    ensure_ascii=False,
                ),
                subscription=WebPushSubscription.model_validate(
                    {
                        "endpoint": subscription.endpoint,
                        "keys": {
                            "p256dh": subscription.p256dh,
                            "auth": subscription.auth,
                        },
                    },
                ),
            )
            response = await self._client.post(
                subscription.endpoint,
                content=message.encrypted,
                headers=dict(message.headers),
            )
        except httpx.RequestError:
            _logger.exception(
                "Web Push transport error for endpoint=%s",
                subscription.endpoint,
            )
            return _PushDeliveryResult(is_gone=False, status_code=None)
        except Exception:
            _logger.exception(
                "Unexpected Web Push error for endpoint=%s",
                subscription.endpoint,
            )
            return _PushDeliveryResult(is_gone=False, status_code=None)
        status = response.status_code
        is_gone = status in _GONE_STATUSES
        if is_gone:
            _logger.info(
                "Web Push: endpoint gone (status=%s) %s",
                status,
                subscription.endpoint,
            )
        elif status >= 300:
            _logger.warning(
                "Web Push delivery failed: status=%s body=%r endpoint=%s",
                status,
                response.text[:500],
                subscription.endpoint,
            )
        else:
            _logger.info(
                "Web Push: ok status=%s endpoint=%s",
                status,
                subscription.endpoint[:80],
            )
        return _PushDeliveryResult(is_gone=is_gone, status_code=status)

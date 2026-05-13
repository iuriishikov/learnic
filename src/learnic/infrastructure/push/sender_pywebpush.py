"""Pywebpush-backed :class:`PushSender` adapter.

``pywebpush`` is sync — it uses ``requests`` under the hood. We
isolate it inside :func:`asyncio.to_thread` so the worker's event
loop can fan out concurrent deliveries through
``asyncio.gather`` without one blocking POST stalling the others.
Errors come back as ``WebPushException`` carrying the HTTP
status; we surface ``410 Gone`` and ``404 Not Found`` as
``is_gone`` so the worker can drop the dead endpoint.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Final

from py_vapid import Vapid01
from pywebpush import WebPushException, webpush
from typing_extensions import override

from learnic.application.common.push.payload import PushPayload
from learnic.application.common.push.sender import (
    PushDeliveryResult,
    PushSender,
)
from learnic.entities.push_subscription.models import PushSubscription
from learnic.infrastructure.configs import WebPushConfig

_logger = logging.getLogger(__name__)

_GONE_STATUSES: Final = frozenset({404, 410})
_DEFAULT_TTL_SECONDS: Final = 60 * 60 * 24


@dataclass(slots=True, frozen=True)
class _PushDeliveryResult:
    is_gone: bool
    status_code: int | None


class PywebpushSender(PushSender):
    """Real-network implementation; no-op when VAPID is not configured.

    A missing or unparseable ``WEBPUSH_VAPID_PRIVATE_KEY``
    (e.g., a developer machine that hasn't generated keys yet)
    makes :meth:`send` log and short-circuit — the rest of the
    system stays functional and the worker won't spam errors.
    Production deployments paste a PEM-encoded private key into
    the env, which flips this back to real delivery.
    """

    def __init__(self, config: WebPushConfig) -> None:
        self._config: Final = config
        self._vapid: Final = self._build_vapid()

    def _build_vapid(self) -> Vapid01 | None:
        raw = self._config.vapid_private_key.strip()
        if not raw:
            return None
        try:
            return Vapid01.from_pem(raw.encode("ascii"))
        except Exception:
            _logger.exception(
                "Failed to parse WEBPUSH_VAPID_PRIVATE_KEY (expected "
                "PEM); pushes disabled.",
            )
            return None

    @override
    async def send(
        self,
        subscription: PushSubscription,
        payload: PushPayload,
    ) -> PushDeliveryResult:
        if self._vapid is None:
            _logger.debug("Web Push send skipped: VAPID is not configured")
            return _PushDeliveryResult(is_gone=False, status_code=None)
        sub_info: dict[str, Any] = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }
        body = json.dumps(
            {
                "title": payload.title,
                "body": payload.body,
                "url": payload.url,
                "tag": payload.tag,
                "icon": payload.icon,
            },
            ensure_ascii=False,
        )
        try:
            response = await asyncio.to_thread(
                _send_blocking,
                sub_info,
                body,
                self._vapid,
                self._config.vapid_subject,
            )
        except WebPushException as exc:
            resp = exc.response
            status = resp.status_code if resp is not None else None
            is_gone = status in _GONE_STATUSES
            if is_gone:
                _logger.info(
                    "Web Push: endpoint gone (status=%s) %s",
                    status,
                    subscription.endpoint,
                )
            else:
                text = resp.text[:500] if resp is not None else None
                _logger.warning(
                    "Web Push delivery failed: status=%s body=%r endpoint=%s",
                    status,
                    text,
                    subscription.endpoint,
                )
            return _PushDeliveryResult(is_gone=is_gone, status_code=status)
        except Exception:
            _logger.exception(
                "Unexpected Web Push error for endpoint=%s",
                subscription.endpoint,
            )
            return _PushDeliveryResult(is_gone=False, status_code=None)
        _logger.info(
            "Web Push: ok status=%s endpoint=%s",
            response.status_code,
            subscription.endpoint[:80],
        )
        return _PushDeliveryResult(is_gone=False, status_code=response.status_code)


def _send_blocking(
    sub_info: dict[str, Any],
    data: str,
    vapid: Vapid01,
    vapid_subject: str,
) -> Any:
    return webpush(
        subscription_info=sub_info,
        data=data,
        vapid_private_key=vapid,
        vapid_claims={"sub": vapid_subject},
        ttl=_DEFAULT_TTL_SECONDS,
    )

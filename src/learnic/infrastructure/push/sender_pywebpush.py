"""Pywebpush-backed :class:`PushSender` adapter.

``pywebpush`` is sync — it uses ``requests`` under the hood. We
isolate it inside :func:`asyncio.to_thread` so the FastAPI event
loop is never blocked by the network round-trip to the push
service. Errors come back as ``WebPushException`` carrying the
HTTP status; we surface ``410 Gone`` and ``404 Not Found`` as
``is_gone`` so the worker can drop the dead endpoint.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Final

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
class _PushDeliveryResult(PushDeliveryResult):
    is_gone: bool
    status_code: int | None


class PywebpushSender(PushSender):
    """Real-network implementation; no-op when VAPID is not configured.

    A missing ``vapid_private_key`` (e.g., in a developer machine
    that hasn't generated keys yet) makes :meth:`send` log and
    short-circuit — the rest of the system stays functional and
    the worker won't spam errors. Production deployments configure
    the keys via env, which flips this back to real delivery.
    """

    def __init__(self, config: WebPushConfig) -> None:
        self._config: Final = config
        self._configured: Final = bool(config.vapid_private_key)
        self._vapid: Final = self._build_vapid()

    def _build_vapid(self) -> object | None:
        """Materialise the VAPID identity once at startup.

        ``pywebpush.webpush`` accepts a ``Vapid01`` object directly
        (preferred) or a string. Strings go through
        :meth:`Vapid01.from_string`, which only understands raw
        URL-safe Base64 of DER bytes — it does NOT auto-detect PEM,
        even though PEM is the convention for env-var keys. We
        sniff for ``BEGIN`` and route to :meth:`Vapid01.from_pem`
        explicitly so operators can paste PEM straight into ``.env``.
        """
        if not self._configured:
            return None
        try:
            from py_vapid import Vapid01
        except ImportError:
            _logger.warning(
                "py_vapid is not installed; cannot prepare VAPID identity.",
            )
            return None
        raw = self._config.vapid_private_key.strip()
        try:
            if "BEGIN" in raw:
                vapid: object = Vapid01.from_pem(raw.encode("ascii"))
            else:
                vapid = Vapid01.from_string(private_key=raw)
        except Exception:
            _logger.exception(
                "Failed to parse WEBPUSH_VAPID_PRIVATE_KEY; pushes disabled.",
            )
            return None
        return vapid

    @override
    async def send(
        self,
        subscription: PushSubscription,
        payload: PushPayload,
    ) -> PushDeliveryResult:
        if not self._configured or self._vapid is None:
            _logger.debug(
                "Web Push send skipped: VAPID keys are not configured",
            )
            return _PushDeliveryResult(is_gone=False, status_code=None)
        try:
            from pywebpush import WebPushException
        except ImportError:
            _logger.warning(
                "pywebpush is not installed; cannot send Web Push.",
            )
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
            status = _status_from_exception(exc)
            is_gone = status in _GONE_STATUSES
            text = _body_from_exception(exc)
            if is_gone:
                _logger.info(
                    "Web Push: endpoint gone (status=%s) %s",
                    status,
                    subscription.endpoint,
                )
            else:
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
        status_code = getattr(response, "status_code", None)
        _logger.info(
            "Web Push: ok status=%s endpoint=%s",
            status_code,
            subscription.endpoint[:80],
        )
        return _PushDeliveryResult(is_gone=False, status_code=status_code)


def _send_blocking(
    sub_info: dict[str, Any],
    data: str,
    vapid: object,
    vapid_subject: str,
) -> object:
    from pywebpush import webpush

    return webpush(
        subscription_info=sub_info,
        data=data,
        vapid_private_key=vapid,
        vapid_claims={"sub": vapid_subject},
        ttl=_DEFAULT_TTL_SECONDS,
    )


def _status_from_exception(exc: object) -> int | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status
    return None


def _body_from_exception(exc: object) -> str | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text[:500]
    return None

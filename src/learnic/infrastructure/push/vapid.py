"""VAPID key helpers shared by the Web Push sender and the key route.

The VAPID identity has a single secret input — the PEM-encoded private
key in ``WEBPUSH_VAPID_PRIVATE_KEY``. Both the signing path (the
sender) and the ``applicationServerKey`` the browser subscribes with
are derived from it here, so the public value can never drift from the
private one.
"""

import base64
import logging
from typing import NewType

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
)

_logger = logging.getLogger(__name__)

# DI marker: the URL-safe Base64 application server key handed to
# browsers (distinct binding from any other ``str`` in the container).
VapidPublicKey = NewType("VapidPublicKey", str)


def load_vapid_private_key(
    private_key_pem: str,
) -> ec.EllipticCurvePrivateKey | None:
    """Parse the VAPID private key, or ``None`` if absent/invalid.

    A missing or unparseable key (e.g. a dev box that has not
    generated keys) returns ``None`` so callers degrade to a logged
    no-op instead of crashing.

    Args:
        private_key_pem: PEM text from ``WEBPUSH_VAPID_PRIVATE_KEY``.

    Returns:
        The loaded P-256 private key, or ``None`` when unset or not a
        valid EC key.
    """
    raw = private_key_pem.strip()
    if not raw:
        return None
    try:
        key = load_pem_private_key(raw.encode("ascii"), password=None)
    except Exception:
        _logger.exception(
            "Failed to parse WEBPUSH_VAPID_PRIVATE_KEY (expected PEM)",
        )
        return None
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        _logger.error("WEBPUSH_VAPID_PRIVATE_KEY is not an EC private key")
        return None
    return key


def application_server_key(private_key_pem: str) -> str:
    """Derive the browser ``applicationServerKey`` from the private key.

    The result is the URL-safe Base64 (unpadded) encoding of the raw
    P-256 public point — the exact shape ``PushManager.subscribe``
    expects. Returns an empty string when no valid key is configured,
    which the SPA already treats as "push not configured".

    Args:
        private_key_pem: PEM text from ``WEBPUSH_VAPID_PRIVATE_KEY``.

    Returns:
        The application server key, or ``""`` when unconfigured.
    """
    key = load_vapid_private_key(private_key_pem)
    if key is None:
        return ""
    point = key.public_key().public_bytes(
        Encoding.X962,
        PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(point).rstrip(b"=").decode("ascii")

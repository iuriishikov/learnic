"""Shared (de)serialisation helpers for spec implementations.

Three building blocks — actor, product ref, collaboration
snapshot — appear inside virtually every kind's payload. Centralise
them here so per-kind specs stay focused on the parts that
actually vary.

Two flavours:

- ``serialize_*`` / ``deserialize_*`` — Redis pub/sub transport,
  carries unmasked refs, round-trippable.
- ``actor_to_ws`` / ``product_to_ws`` / ``collaboration_to_ws``
  — public WS wire format (masked email, derived ``full_name``).
  Same dict shape as the REST Pydantic schemas, so the discriminated
  union there validates exactly what we emit.
"""

import uuid
from datetime import datetime
from typing import Any

from learnic.application.common.formatting import build_full_name, mask_email
from learnic.application.common.notifications.views import (
    CollaborationSnapshotView,
    GiftSnapshotView,
    ProductRefView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.user.models import UserID


# --------------------------- Redis transport --------------------------- #


def serialize_actor(actor: UserRefView | None) -> dict[str, Any] | None:
    if actor is None:
        return None
    return {
        "oid": str(actor.oid),
        "email": actor.email,
        "first_name": actor.first_name,
        "last_name": actor.last_name,
        "patronymic": actor.patronymic,
    }


def deserialize_actor(data: dict[str, Any] | None) -> UserRefView | None:
    if data is None:
        return None
    return UserRefView(
        oid=UserID(uuid.UUID(data["oid"])),
        email=data.get("email", ""),
        first_name=data["first_name"],
        last_name=data["last_name"],
        patronymic=data.get("patronymic"),
    )


def deserialize_actor_required(
    data: dict[str, Any] | None,
    kind_name: str,
) -> UserRefView:
    actor = deserialize_actor(data)
    if actor is None:
        raise ValueError(f"{kind_name} requires a non-null actor field")
    return actor


def serialize_product(product: ProductRefView) -> dict[str, Any]:
    return {"oid": str(product.oid), "name": product.name}


def deserialize_product(data: dict[str, Any]) -> ProductRefView:
    return ProductRefView(
        oid=ProductID(uuid.UUID(data["oid"])),
        name=data["name"],
    )


def serialize_collaboration(
    snapshot: CollaborationSnapshotView | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "status": snapshot.status.value,
        "accepted_at": _isoformat(snapshot.accepted_at),
        "declined_at": _isoformat(snapshot.declined_at),
        "revoked_at": _isoformat(snapshot.revoked_at),
        "invite_expires_at": _isoformat(snapshot.invite_expires_at),
    }


def deserialize_collaboration(
    data: dict[str, Any] | None,
) -> CollaborationSnapshotView | None:
    if data is None:
        return None
    return CollaborationSnapshotView(
        status=CollaborationStatus(data["status"]),
        accepted_at=_parse_iso(data.get("accepted_at")),
        declined_at=_parse_iso(data.get("declined_at")),
        revoked_at=_parse_iso(data.get("revoked_at")),
        invite_expires_at=_parse_iso(data.get("invite_expires_at")),
    )


def serialize_gift(
    snapshot: GiftSnapshotView | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "status": snapshot.status.value,
        "accepted_at": _isoformat(snapshot.accepted_at),
        "declined_at": _isoformat(snapshot.declined_at),
        "revoked_at": _isoformat(snapshot.revoked_at),
        "invite_expires_at": _isoformat(snapshot.invite_expires_at),
    }


def deserialize_gift(
    data: dict[str, Any] | None,
) -> GiftSnapshotView | None:
    if data is None:
        return None
    return GiftSnapshotView(
        status=GiftStatus(data["status"]),
        accepted_at=_parse_iso(data.get("accepted_at")),
        declined_at=_parse_iso(data.get("declined_at")),
        revoked_at=_parse_iso(data.get("revoked_at")),
        invite_expires_at=_parse_iso(data.get("invite_expires_at")),
    )


# ----------------------------- WS wire --------------------------------- #


def actor_to_ws(actor: UserRefView | None) -> dict[str, Any] | None:
    if actor is None:
        return None
    return {
        "oid": str(actor.oid),
        "full_name": build_full_name(
            actor.first_name,
            actor.last_name,
            actor.patronymic,
        ),
        "email": mask_email(actor.email) if actor.email else "",
    }


def product_to_ws(product: ProductRefView) -> dict[str, Any]:
    return {"oid": str(product.oid), "name": product.name}


def collaboration_to_ws(
    snapshot: CollaborationSnapshotView | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "status": snapshot.status.value,
        "accepted_at": _isoformat(snapshot.accepted_at),
        "declined_at": _isoformat(snapshot.declined_at),
        "revoked_at": _isoformat(snapshot.revoked_at),
        "invite_expires_at": _isoformat(snapshot.invite_expires_at),
    }


def gift_to_ws(
    snapshot: GiftSnapshotView | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "status": snapshot.status.value,
        "accepted_at": _isoformat(snapshot.accepted_at),
        "declined_at": _isoformat(snapshot.declined_at),
        "revoked_at": _isoformat(snapshot.revoked_at),
        "invite_expires_at": _isoformat(snapshot.invite_expires_at),
    }


# ------------------------------- utils --------------------------------- #


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None

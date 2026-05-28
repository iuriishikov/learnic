"""Typed payloads for the product-level WebSocket channel.

Mirrors the design in
:mod:`learnic.application.common.collaboration.payloads`:

* one frozen dataclass per kind,
* class-level :attr:`KIND` constant as the envelope discriminator
  (a ``ClassVar`` — invisible to :func:`dataclasses.asdict` so the
  wire payload sub-object stays clean),
* closed :data:`ProductPayload` union — mypy flags every consumer
  that does not handle a new variant,
* ``from_*`` classmethods that centralise projections from domain
  entities into the wire shape.

Wire shape: ``dataclasses.asdict(payload)`` produces the payload
sub-object the SPA expects; the bus serializer adds the envelope
(``kind`` from ``type(payload).KIND``, ``product_id``,
``actor_id``, ``occurred_at``).
"""

from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.role.ids import RoleID
from learnic.entities.role.models import Role
from learnic.entities.tag.models import Tag
from learnic.entities.user.models import UserID


# ---------------------------------------------------------------- #
# Product metadata payloads.
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class NameChangedPayload:
    KIND: ClassVar[Literal["name_changed"]] = "name_changed"
    name: str


@dataclass(slots=True, frozen=True)
class DescriptionChangedPayload:
    KIND: ClassVar[Literal["description_changed"]] = "description_changed"
    description: str


@dataclass(slots=True, frozen=True)
class DurationChangedPayload:
    KIND: ClassVar[Literal["duration_changed"]] = "duration_changed"
    total_duration_in_hours: int


@dataclass(slots=True, frozen=True)
class PriceChangedPayload:
    KIND: ClassVar[Literal["price_changed"]] = "price_changed"
    amount: int


@dataclass(slots=True, frozen=True)
class CoverChangedPayload:
    KIND: ClassVar[Literal["cover_changed"]] = "cover_changed"
    cover_file_id: str


@dataclass(slots=True, frozen=True)
class CoverRemovedPayload:
    KIND: ClassVar[Literal["cover_removed"]] = "cover_removed"


@dataclass(slots=True, frozen=True)
class PublishedPayload:
    KIND: ClassVar[Literal["published"]] = "published"
    status: str
    published_at: str


@dataclass(slots=True, frozen=True)
class ArchivedPayload:
    KIND: ClassVar[Literal["archived"]] = "archived"
    status: str


@dataclass(slots=True, frozen=True)
class UnarchivedPayload:
    KIND: ClassVar[Literal["unarchived"]] = "unarchived"
    status: str


@dataclass(slots=True, frozen=True)
class VisibilityChangedPayload:
    KIND: ClassVar[Literal["visibility_changed"]] = "visibility_changed"
    visibility: str


@dataclass(slots=True, frozen=True)
class DeletedPayload:
    KIND: ClassVar[Literal["deleted"]] = "deleted"


# ---------------------------------------------------------------- #
# Q&A payloads.
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class QaAddedPayload:
    KIND: ClassVar[Literal["qa_added"]] = "qa_added"
    qa_id: str
    question: str
    answer: str
    position: int


@dataclass(slots=True, frozen=True)
class QaQuestionChangedPayload:
    KIND: ClassVar[Literal["qa_question_changed"]] = "qa_question_changed"
    qa_id: str
    question: str


@dataclass(slots=True, frozen=True)
class QaAnswerChangedPayload:
    KIND: ClassVar[Literal["qa_answer_changed"]] = "qa_answer_changed"
    qa_id: str
    answer: str


@dataclass(slots=True, frozen=True)
class QaReorderedPayload:
    KIND: ClassVar[Literal["qa_reordered"]] = "qa_reordered"
    qa_id: str
    position: int


@dataclass(slots=True, frozen=True)
class QaDeletedPayload:
    KIND: ClassVar[Literal["qa_deleted"]] = "qa_deleted"
    qa_id: str


# ---------------------------------------------------------------- #
# Collaboration payloads.
#
# All five kinds share the same instance shape — only the
# discriminator differs. ``collaborator_id`` is present once the
# invite has been accepted (or for ``COLLABORATION_INVITED`` when
# the invitee is an existing user); ``invited_email`` is set for
# by-email invites where no user account exists yet. Either is
# enough for the SPA to identify the affected entry.
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class CollaborationInvitedPayload:
    KIND: ClassVar[Literal["collaboration_invited"]] = "collaboration_invited"
    collaboration_id: str
    collaborator_id: str | None = None
    invited_email: str | None = None

    @classmethod
    def of(
        cls,
        *,
        collaboration_id: ProductCollaborationID,
        collaborator_id: UserID | None = None,
        invited_email: str | None = None,
    ) -> "CollaborationInvitedPayload":
        return cls(
            collaboration_id=str(collaboration_id),
            collaborator_id=(
                str(collaborator_id) if collaborator_id is not None else None
            ),
            invited_email=invited_email,
        )


@dataclass(slots=True, frozen=True)
class CollaborationAcceptedPayload:
    KIND: ClassVar[Literal["collaboration_accepted"]] = "collaboration_accepted"
    collaboration_id: str
    collaborator_id: str | None = None
    invited_email: str | None = None

    @classmethod
    def of(
        cls,
        *,
        collaboration_id: ProductCollaborationID,
        collaborator_id: UserID,
    ) -> "CollaborationAcceptedPayload":
        return cls(
            collaboration_id=str(collaboration_id),
            collaborator_id=str(collaborator_id),
        )


@dataclass(slots=True, frozen=True)
class CollaborationDeclinedPayload:
    KIND: ClassVar[Literal["collaboration_declined"]] = "collaboration_declined"
    collaboration_id: str
    collaborator_id: str | None = None
    invited_email: str | None = None

    @classmethod
    def of(
        cls,
        *,
        collaboration_id: ProductCollaborationID,
        collaborator_id: UserID,
    ) -> "CollaborationDeclinedPayload":
        return cls(
            collaboration_id=str(collaboration_id),
            collaborator_id=str(collaborator_id),
        )


@dataclass(slots=True, frozen=True)
class CollaborationRevokedPayload:
    KIND: ClassVar[Literal["collaboration_revoked"]] = "collaboration_revoked"
    collaboration_id: str
    collaborator_id: str | None = None
    invited_email: str | None = None

    @classmethod
    def of(
        cls,
        *,
        collaboration_id: ProductCollaborationID,
        collaborator_id: UserID | None = None,
    ) -> "CollaborationRevokedPayload":
        return cls(
            collaboration_id=str(collaboration_id),
            collaborator_id=(
                str(collaborator_id) if collaborator_id is not None else None
            ),
        )


@dataclass(slots=True, frozen=True)
class CollaborationGrantsUpdatedPayload:
    KIND: ClassVar[Literal["collaboration_grants_updated"]] = (
        "collaboration_grants_updated"
    )
    collaboration_id: str
    collaborator_id: str | None = None
    invited_email: str | None = None

    @classmethod
    def of(
        cls,
        *,
        collaboration_id: ProductCollaborationID,
        collaborator_id: UserID | None,
    ) -> "CollaborationGrantsUpdatedPayload":
        return cls(
            collaboration_id=str(collaboration_id),
            collaborator_id=(
                str(collaborator_id) if collaborator_id is not None else None
            ),
        )


# ---------------------------------------------------------------- #
# Role payloads.
#
# ``role_created`` / ``role_updated`` spread the role fields
# directly into the payload (no ``role`` sub-object) — that is
# the SPA contract, mirroring ``RoleSchema`` from
# ``GET /roles/{id}`` so the SPA can splice a single row into
# its catalogue cache without a refetch. ``role_deleted`` carries
# only the id. The two non-deleted classes share the projection
# helper :func:`_role_wire_fields`.
# ---------------------------------------------------------------- #


def _role_wire_fields(role: Role) -> dict[str, Any]:
    """Project a loaded :class:`Role` into the wire-shape fields.

    Shared by :meth:`RoleCreatedPayload.from_entity` and
    :meth:`RoleUpdatedPayload.from_entity`. ``permissions`` is
    sorted lexicographically for deterministic envelopes.
    """
    if role.permissions is None:
        msg = "role.permissions must be loaded before publishing a role event"
        raise AssertionError(msg)
    return {
        "oid": str(role.oid),
        "product_id": str(role.product_id),
        "name": role.name.value,
        "description": (
            role.description.value if role.description is not None else None
        ),
        "position": role.position.value,
        "permissions": sorted(p.value for p in role.permissions.permissions),
        "created_by": (str(role.created_by) if role.created_by is not None else None),
        "created_at": role.created_at.isoformat(),
        "updated_at": role.updated_at.isoformat(),
    }


@dataclass(slots=True, frozen=True)
class RoleCreatedPayload:
    KIND: ClassVar[Literal["role_created"]] = "role_created"
    oid: str
    product_id: str
    name: str
    description: str | None
    position: int
    permissions: list[str]
    created_by: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, role: Role) -> "RoleCreatedPayload":
        return cls(**_role_wire_fields(role))


@dataclass(slots=True, frozen=True)
class RoleUpdatedPayload:
    KIND: ClassVar[Literal["role_updated"]] = "role_updated"
    oid: str
    product_id: str
    name: str
    description: str | None
    position: int
    permissions: list[str]
    created_by: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, role: Role) -> "RoleUpdatedPayload":
        return cls(**_role_wire_fields(role))


@dataclass(slots=True, frozen=True)
class RoleDeletedPayload:
    KIND: ClassVar[Literal["role_deleted"]] = "role_deleted"
    role_id: str

    @classmethod
    def of(cls, role_id: RoleID) -> "RoleDeletedPayload":
        return cls(role_id=str(role_id))


# ---------------------------------------------------------------- #
# Tag payloads.
#
# A product's tag list is mutated in one shot
# (``PUT /products/{product_id}/tags``), so a single
# ``tags_changed`` payload carries the new ordered list. The SPA
# replaces the cached ``product.tags`` array verbatim — no
# per-item add/remove events. Order in the payload mirrors the
# order in storage (``product_tags.position`` ascending).
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class TagsChangedPayload:
    KIND: ClassVar[Literal["tags_changed"]] = "tags_changed"
    tags: list[dict[str, str]]

    @classmethod
    def of(cls, tags: list[Tag]) -> "TagsChangedPayload":
        return cls(
            tags=[
                {
                    "oid": str(tag.oid),
                    "name": tag.name.value,
                    "color": tag.color.value,
                }
                for tag in tags
            ],
        )


# ---------------------------------------------------------------- #
# Gift payloads.
#
# A product's "Gifts" tab lists every issued gift and its lifecycle
# status (``pending_invite`` → ``accepted`` / ``declined`` /
# ``revoked``). Each transition emits one kind so collaborators
# watching the editor see the tab update without a manual refresh.
# The payload carries only ``gift_id``: the SPA refetches the
# permission-gated gift list rather than splicing a single row, the
# same invalidate-and-refetch policy already used for collaboration
# events. ``gift_id`` lets the SPA scope/log the change; the email
# of an unregistered invitee is deliberately NOT on the wire (unlike
# collaboration invites) so it never reaches a collaborator who only
# has editor access — the gift list endpoint gates that field.
# ---------------------------------------------------------------- #


@dataclass(slots=True, frozen=True)
class GiftIssuedPayload:
    KIND: ClassVar[Literal["gift_issued"]] = "gift_issued"
    gift_id: str

    @classmethod
    def of(cls, gift_id: ProductGiftID) -> "GiftIssuedPayload":
        return cls(gift_id=str(gift_id))


@dataclass(slots=True, frozen=True)
class GiftAcceptedPayload:
    KIND: ClassVar[Literal["gift_accepted"]] = "gift_accepted"
    gift_id: str

    @classmethod
    def of(cls, gift_id: ProductGiftID) -> "GiftAcceptedPayload":
        return cls(gift_id=str(gift_id))


@dataclass(slots=True, frozen=True)
class GiftDeclinedPayload:
    KIND: ClassVar[Literal["gift_declined"]] = "gift_declined"
    gift_id: str

    @classmethod
    def of(cls, gift_id: ProductGiftID) -> "GiftDeclinedPayload":
        return cls(gift_id=str(gift_id))


@dataclass(slots=True, frozen=True)
class GiftRevokedPayload:
    KIND: ClassVar[Literal["gift_revoked"]] = "gift_revoked"
    gift_id: str

    @classmethod
    def of(cls, gift_id: ProductGiftID) -> "GiftRevokedPayload":
        return cls(gift_id=str(gift_id))


ProductPayload = (
    NameChangedPayload
    | DescriptionChangedPayload
    | DurationChangedPayload
    | PriceChangedPayload
    | CoverChangedPayload
    | CoverRemovedPayload
    | PublishedPayload
    | ArchivedPayload
    | UnarchivedPayload
    | VisibilityChangedPayload
    | DeletedPayload
    | QaAddedPayload
    | QaQuestionChangedPayload
    | QaAnswerChangedPayload
    | QaReorderedPayload
    | QaDeletedPayload
    | CollaborationInvitedPayload
    | CollaborationAcceptedPayload
    | CollaborationDeclinedPayload
    | CollaborationRevokedPayload
    | CollaborationGrantsUpdatedPayload
    | RoleCreatedPayload
    | RoleUpdatedPayload
    | RoleDeletedPayload
    | TagsChangedPayload
    | GiftIssuedPayload
    | GiftAcceptedPayload
    | GiftDeclinedPayload
    | GiftRevokedPayload
)


def payload_from_wire(kind: str, data: dict[str, Any]) -> ProductPayload:
    """Reconstruct a typed payload from its on-wire dict shape.

    The inverse of ``dataclasses.asdict(payload)`` — used by the
    Redis subscriber to rebuild typed events as they arrive. The
    ``kind`` comes from the envelope; ``data`` is the inner
    payload sub-object.
    """
    if kind == NameChangedPayload.KIND:
        return NameChangedPayload(name=data["name"])
    if kind == DescriptionChangedPayload.KIND:
        return DescriptionChangedPayload(description=data["description"])
    if kind == DurationChangedPayload.KIND:
        return DurationChangedPayload(
            total_duration_in_hours=data["total_duration_in_hours"],
        )
    if kind == PriceChangedPayload.KIND:
        return PriceChangedPayload(amount=data["amount"])
    if kind == CoverChangedPayload.KIND:
        return CoverChangedPayload(cover_file_id=data["cover_file_id"])
    if kind == CoverRemovedPayload.KIND:
        return CoverRemovedPayload()
    if kind == PublishedPayload.KIND:
        return PublishedPayload(
            status=data["status"],
            published_at=data["published_at"],
        )
    if kind == ArchivedPayload.KIND:
        return ArchivedPayload(status=data["status"])
    if kind == UnarchivedPayload.KIND:
        return UnarchivedPayload(status=data["status"])
    if kind == VisibilityChangedPayload.KIND:
        return VisibilityChangedPayload(visibility=data["visibility"])
    if kind == DeletedPayload.KIND:
        return DeletedPayload()
    if kind == QaAddedPayload.KIND:
        return QaAddedPayload(
            qa_id=data["qa_id"],
            question=data["question"],
            answer=data["answer"],
            position=data["position"],
        )
    if kind == QaQuestionChangedPayload.KIND:
        return QaQuestionChangedPayload(
            qa_id=data["qa_id"],
            question=data["question"],
        )
    if kind == QaAnswerChangedPayload.KIND:
        return QaAnswerChangedPayload(
            qa_id=data["qa_id"],
            answer=data["answer"],
        )
    if kind == QaReorderedPayload.KIND:
        return QaReorderedPayload(
            qa_id=data["qa_id"],
            position=data["position"],
        )
    if kind == QaDeletedPayload.KIND:
        return QaDeletedPayload(qa_id=data["qa_id"])
    if kind == CollaborationInvitedPayload.KIND:
        return CollaborationInvitedPayload(
            collaboration_id=data["collaboration_id"],
            collaborator_id=data.get("collaborator_id"),
            invited_email=data.get("invited_email"),
        )
    if kind == CollaborationAcceptedPayload.KIND:
        return CollaborationAcceptedPayload(
            collaboration_id=data["collaboration_id"],
            collaborator_id=data.get("collaborator_id"),
            invited_email=data.get("invited_email"),
        )
    if kind == CollaborationDeclinedPayload.KIND:
        return CollaborationDeclinedPayload(
            collaboration_id=data["collaboration_id"],
            collaborator_id=data.get("collaborator_id"),
            invited_email=data.get("invited_email"),
        )
    if kind == CollaborationRevokedPayload.KIND:
        return CollaborationRevokedPayload(
            collaboration_id=data["collaboration_id"],
            collaborator_id=data.get("collaborator_id"),
            invited_email=data.get("invited_email"),
        )
    if kind == CollaborationGrantsUpdatedPayload.KIND:
        return CollaborationGrantsUpdatedPayload(
            collaboration_id=data["collaboration_id"],
            collaborator_id=data.get("collaborator_id"),
            invited_email=data.get("invited_email"),
        )
    if kind == RoleCreatedPayload.KIND:
        return RoleCreatedPayload(
            oid=data["oid"],
            product_id=data["product_id"],
            name=data["name"],
            description=data["description"],
            position=data["position"],
            permissions=list(data["permissions"]),
            created_by=data["created_by"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
    if kind == RoleUpdatedPayload.KIND:
        return RoleUpdatedPayload(
            oid=data["oid"],
            product_id=data["product_id"],
            name=data["name"],
            description=data["description"],
            position=data["position"],
            permissions=list(data["permissions"]),
            created_by=data["created_by"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
    if kind == RoleDeletedPayload.KIND:
        return RoleDeletedPayload(role_id=data["role_id"])
    if kind == TagsChangedPayload.KIND:
        return TagsChangedPayload(tags=list(data["tags"]))
    if kind == GiftIssuedPayload.KIND:
        return GiftIssuedPayload(gift_id=data["gift_id"])
    if kind == GiftAcceptedPayload.KIND:
        return GiftAcceptedPayload(gift_id=data["gift_id"])
    if kind == GiftDeclinedPayload.KIND:
        return GiftDeclinedPayload(gift_id=data["gift_id"])
    if kind == GiftRevokedPayload.KIND:
        return GiftRevokedPayload(gift_id=data["gift_id"])
    msg = f"unknown product payload kind: {kind!r}"
    raise ValueError(msg)

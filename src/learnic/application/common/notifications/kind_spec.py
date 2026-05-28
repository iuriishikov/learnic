"""Per-kind specification — single source of truth for a notification kind.

Adding a new kind on the backend used to require editing ~10
modules with parallel ``isinstance`` ladders (gateway, reader,
Redis bus, REST route, WS route, push-text switch). This module
defines the abstraction those switches dispatch through.

A spec bundles everything that varies between kinds:

- Domain glue — the ``Details`` / ``View`` dataclasses, the
  factory that builds a fresh :class:`Notification`, the
  ``category`` it belongs to, and the push-banner copy.
- Reference resolution — the spec declares which products /
  users / collaborations its details point at via
  :meth:`references`, and the reader hydrates them in batch.
  :meth:`to_view` then composes the final view from the
  resolved bag.
- Internal Redis transport — :meth:`serialize_view` /
  :meth:`deserialize_view` round-trip the view across the
  pub/sub channel between the publisher and the WS subscriber.
- WS wire format — :meth:`to_ws_dict` produces the
  client-facing dict (with masked email, derived ``full_name``).
  REST schemas validate the same dict via Pydantic, so the
  WS dict is the single source of truth for both wire surfaces.

Persistence — the ``sa.Table`` and SA Core insert/select glue —
lives in a sibling Protocol declared in the infrastructure layer
(``infrastructure/notifications/specs/_persistence.py``) so this
module stays free of SQLAlchemy. Concrete classes implement both
Protocols simultaneously and live in
``infrastructure/notifications/specs/<kind>.py``.

Registration is a plain :class:`NotificationKindRegistry`
populated once at startup (see ``ioc.py``); the gateway, reader,
Redis bus, REST route, WS route, and publisher all dispatch
through it.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Final, Protocol, TypeVar

from learnic.application.common.email.components import EmailParagraph
from learnic.application.common.notifications.channels import (
    ChannelPayload,
    EmailPayload,
    InAppPayload,
    PushPayload,
)
from learnic.application.common.notifications.views import (
    CollaborationSnapshotView,
    GiftSnapshotView,
    NotificationDetailsView,
    ProductRefView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.entities.notification.enums import NotificationChannel
from learnic.entities.notification.details import NotificationDetails
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.user.models import UserID

D = TypeVar("D", bound=NotificationDetails, contravariant=True)
V = TypeVar("V")


@dataclass(slots=True)
class RefRequest:
    """What entities a notification's details point at.

    Each spec returns one of these from :meth:`NotificationKindSpec.references`.
    The reader merges them across every loaded notification and runs one
    batched ``IN`` query per entity type.

    ``products_needing_manage_perm`` is the subset of products for which
    the SPA needs the recipient's current ``MANAGE_COLLABORATORS`` flag
    (drives revoke / re-invite CTA visibility on the corresponding card).
    """

    product_ids: set[ProductID] = field(default_factory=set)
    user_ids: set[UserID] = field(default_factory=set)
    collaboration_ids: set[ProductCollaborationID] = field(default_factory=set)
    gift_ids: set[ProductGiftID] = field(default_factory=set)
    products_needing_manage_perm: set[ProductID] = field(default_factory=set)
    session_family_ids: set[uuid.UUID] = field(default_factory=set)

    def merge(self, other: "RefRequest") -> None:
        self.product_ids |= other.product_ids
        self.user_ids |= other.user_ids
        self.collaboration_ids |= other.collaboration_ids
        self.gift_ids |= other.gift_ids
        self.products_needing_manage_perm |= other.products_needing_manage_perm
        self.session_family_ids |= other.session_family_ids

    @classmethod
    def empty(cls) -> "RefRequest":
        return cls()


def _user_ref_placeholder(user_id: UserID) -> UserRefView:
    """Defensive fallback for a user row that vanished mid-flight.

    The HTTP boundary requires a non-empty ``full_name``, so we
    return a single-character bullet rather than empty strings —
    keeps Pydantic validation happy for the rare race where a
    user was deleted between the notification insert and the
    read-time JOIN.
    """
    return UserRefView(
        oid=user_id,
        email="",
        first_name="—",
        last_name="",
        patronymic=None,
    )


@dataclass(slots=True)
class ResolvedRefs:
    """Hydrated entities the reader resolved for a batch of notifications.

    Each lookup falls back to a stub so a vanished row doesn't
    break the projection — same defensive behaviour the legacy
    per-kind branches had, just centralised here.

    :class:`CollaborationSnapshotView` lookups return ``None``
    when the collaboration row is missing (panels treat that as
    ``unavailable``); product / user lookups have non-null
    placeholders because the HTTP boundary rejects empty values.
    """

    products: dict[ProductID, ProductRefView] = field(default_factory=dict)
    users: dict[UserID, UserRefView] = field(default_factory=dict)
    collaborations: dict[
        ProductCollaborationID,
        CollaborationSnapshotView,
    ] = field(default_factory=dict)
    gifts: dict[ProductGiftID, GiftSnapshotView] = field(default_factory=dict)
    manage_perms: dict[ProductID, bool] = field(default_factory=dict)
    session_active: dict[uuid.UUID, bool] = field(default_factory=dict)

    def product(self, oid: ProductID) -> ProductRefView:
        return self.products.get(oid) or ProductRefView(oid=oid, name="")

    def user(self, oid: UserID) -> UserRefView:
        return self.users.get(oid) or _user_ref_placeholder(oid)

    def collaboration(
        self,
        oid: ProductCollaborationID,
    ) -> CollaborationSnapshotView | None:
        return self.collaborations.get(oid)

    def gift(self, oid: ProductGiftID) -> GiftSnapshotView | None:
        return self.gifts.get(oid)

    def can_manage(self, product_id: ProductID) -> bool:
        return self.manage_perms.get(product_id, False)

    def is_session_active(self, family_id: uuid.UUID) -> bool:
        """True iff a refresh-token row exists for the family with no
        ``revoked_at`` and an ``expires_at`` in the future. Defaults to
        ``False`` so callers treat a vanished session as already gone.
        """
        return self.session_active.get(family_id, False)


class NotificationKindSpec(Protocol[D, V]):
    """Per-kind contract — domain glue + Redis/WS wire format.

    Concrete implementations live in
    ``infrastructure/notifications/specs/<kind>.py`` and also
    implement the sibling persistence Protocol declared there.
    Application-layer code (publisher, Redis bus serializer,
    WS handler) should depend only on this Protocol.
    """

    kind: ClassVar[NotificationKind]
    category: ClassVar[NotificationCategory]
    details_cls: ClassVar[type]
    view_cls: ClassVar[type]
    push_title: ClassVar[str]
    push_body: ClassVar[str]
    # Email channel — same minimal copy contract as push: a static
    # subject + plain-text body. Personalisation (actor name,
    # product name) requires the resolved view; if a future kind
    # needs it, override :meth:`render` to build a richer payload
    # from the hydrated view.
    email_subject: ClassVar[str]
    email_body: ClassVar[str]

    def render(
        self,
        channel: NotificationChannel,
        view: V,
    ) -> ChannelPayload | None:
        """Return the per-channel payload for ``channel``.

        Default implementation reads the ``push_*`` / ``email_*``
        ClassVars and synthesises the standard payloads. Specs that
        need richer or channel-specific copy (email with CTA button,
        push with deep-link URL, future SMS / Telegram payloads)
        override this method and inspect ``view`` for personalisation.

        Returning ``None`` means "this kind has nothing to send on
        this channel" — the dispatcher skips the channel silently.
        Adding a new :class:`NotificationChannel` variant requires
        no edits here: existing specs automatically return ``None``
        for the unknown channel and the new channel's implementer
        opts kinds in by overriding :meth:`render`.
        """
        cls = type(self)
        if channel is NotificationChannel.EMAIL:
            return EmailPayload(
                subject=cls.email_subject,
                components=[EmailParagraph.text(cls.email_body)],
            )
        if channel is NotificationChannel.PUSH:
            return PushPayload(
                title=cls.push_title,
                body=cls.push_body,
                category=cls.category.value,
            )
        if channel is NotificationChannel.IN_APP:
            return InAppPayload(view=view)
        return None

    def references(self, details: D) -> RefRequest:
        """Declare which products / users / collaborations ``details`` points at.

        The reader merges the requests across a batch and resolves
        each entity type with a single ``IN`` lookup.
        """
        ...

    def to_view(self, details: D, refs: ResolvedRefs) -> V:
        """Compose the final view from the loaded details + hydrated refs."""
        ...

    def serialize_view(self, view: V) -> dict[str, Any]:
        """Serialise ``view`` for Redis pub/sub transport.

        Round-trippable with :meth:`deserialize_view`. Carries
        unmasked refs — masking happens at the WS / REST boundary
        via :meth:`to_ws_dict` and the corresponding Pydantic
        schemas.
        """
        ...

    def deserialize_view(self, data: dict[str, Any]) -> V:
        """Inverse of :meth:`serialize_view` for the WS subscriber."""
        ...

    def to_ws_dict(self, view: V) -> dict[str, Any]:
        """Wire-format dict for ``WS /users/me/notifications``.

        Same shape that REST returns — Pydantic models in the
        REST route validate the output of this method via the
        discriminated union, so the dict is the single source
        of truth for both wire surfaces.

        The ``"type"`` discriminator key is *not* added here —
        the registry adds it from :attr:`kind` so concrete specs
        cannot drift from the enum value.
        """
        ...


@dataclass(slots=True, frozen=True)
class _RegistryIndex:
    by_kind: dict[NotificationKind, NotificationKindSpec[Any, Any]]
    by_details: dict[type, NotificationKindSpec[Any, Any]]
    by_view: dict[type, NotificationKindSpec[Any, Any]]


class NotificationKindRegistry:
    """Lookup table: kind ↔ details type ↔ view type ↔ spec.

    Registering a new kind = appending one spec instance to the
    list passed to :meth:`__init__`. Every dispatcher (gateway,
    reader, Redis bus, WS, REST, publisher) goes through this
    object so nothing else has to learn about new kinds.
    """

    def __init__(
        self,
        specs: list[NotificationKindSpec[Any, Any]],
    ) -> None:
        by_kind: dict[NotificationKind, NotificationKindSpec[Any, Any]] = {}
        by_details: dict[type, NotificationKindSpec[Any, Any]] = {}
        by_view: dict[type, NotificationKindSpec[Any, Any]] = {}
        for spec in specs:
            if spec.kind in by_kind:
                raise ValueError(
                    f"Duplicate notification kind in registry: {spec.kind!r}",
                )
            by_kind[spec.kind] = spec
            by_details[spec.details_cls] = spec
            by_view[spec.view_cls] = spec
        self._index: Final = _RegistryIndex(
            by_kind=by_kind,
            by_details=by_details,
            by_view=by_view,
        )

    def by_kind(self, kind: NotificationKind) -> NotificationKindSpec[Any, Any]:
        try:
            return self._index.by_kind[kind]
        except KeyError as exc:
            raise LookupError(
                f"No spec registered for kind: {kind!r}",
            ) from exc

    def by_details_type(
        self,
        details_cls: type,
    ) -> NotificationKindSpec[Any, Any]:
        try:
            return self._index.by_details[details_cls]
        except KeyError as exc:
            raise LookupError(
                f"No spec registered for details type: {details_cls.__name__}",
            ) from exc

    def by_view_type(
        self,
        view_cls: type,
    ) -> NotificationKindSpec[Any, Any]:
        try:
            return self._index.by_view[view_cls]
        except KeyError as exc:
            raise LookupError(
                f"No spec registered for view type: {view_cls.__name__}",
            ) from exc

    def by_view(
        self,
        view: NotificationDetailsView,
    ) -> NotificationKindSpec[Any, Any]:
        return self.by_view_type(type(view))

    def all(self) -> list[NotificationKindSpec[Any, Any]]:
        return list(self._index.by_kind.values())


def make_notification(
    *,
    spec: NotificationKindSpec[D, V],
    recipient_id: UserID,
    actor_id: UserID | None,
    details: D,
    now: datetime | None = None,
) -> Notification:
    """Build a fresh :class:`Notification` for the given spec + details.

    Producers call this from their command handler; the spec
    contributes ``kind`` and ``category`` so the caller never has
    to remember the right tab grouping.
    """
    moment = now or datetime.now(timezone.utc)
    return Notification(
        oid=NotificationID(uuid.uuid4()),
        recipient_id=recipient_id,
        kind=spec.kind,
        category=spec.category,
        actor_id=actor_id,
        created_at=moment,
        read_at=None,
        details=details,
    )

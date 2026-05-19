from learnic.application.common.events import publish_event
from learnic.application.common.product_events.event_bus import (
    ProductEventBus,
)
from learnic.application.common.product_events.events import ProductEvent
from learnic.application.common.product_events.payloads import (
    ArchivedPayload,
    CollaborationAcceptedPayload,
    CollaborationDeclinedPayload,
    CollaborationGrantsUpdatedPayload,
    CollaborationInvitedPayload,
    CollaborationRevokedPayload,
    CoverChangedPayload,
    CoverRemovedPayload,
    DeletedPayload,
    DescriptionChangedPayload,
    DurationChangedPayload,
    NameChangedPayload,
    PriceChangedPayload,
    ProductPayload,
    PublishedPayload,
    QaAddedPayload,
    QaAnswerChangedPayload,
    QaDeletedPayload,
    QaQuestionChangedPayload,
    QaReorderedPayload,
    RoleCreatedPayload,
    RoleDeletedPayload,
    RoleUpdatedPayload,
    TagsChangedPayload,
    UnarchivedPayload,
    WebinarDefaultsUpdatedPayload,
    payload_from_wire,
)

# Alias for migration ergonomics — handlers depend on
# ``publish_product_event`` for documentation value, but it is
# the generic helper under the hood.
publish_product_event = publish_event


__all__ = [
    "ArchivedPayload",
    "CollaborationAcceptedPayload",
    "CollaborationDeclinedPayload",
    "CollaborationGrantsUpdatedPayload",
    "CollaborationInvitedPayload",
    "CollaborationRevokedPayload",
    "CoverChangedPayload",
    "CoverRemovedPayload",
    "DeletedPayload",
    "DescriptionChangedPayload",
    "DurationChangedPayload",
    "NameChangedPayload",
    "PriceChangedPayload",
    "ProductEvent",
    "ProductEventBus",
    "ProductPayload",
    "PublishedPayload",
    "QaAddedPayload",
    "QaAnswerChangedPayload",
    "QaDeletedPayload",
    "QaQuestionChangedPayload",
    "QaReorderedPayload",
    "RoleCreatedPayload",
    "RoleDeletedPayload",
    "RoleUpdatedPayload",
    "TagsChangedPayload",
    "UnarchivedPayload",
    "WebinarDefaultsUpdatedPayload",
    "payload_from_wire",
    "publish_product_event",
]

"""Per-kind notification specs and the registry that bundles them.

Each ``<kind>.py`` module defines one class that implements both
the application-layer
:class:`learnic.application.common.notifications.kind_spec.NotificationKindSpec`
(domain glue, Redis transport, WS wire format) and the
infrastructure-layer
:class:`learnic.infrastructure.notifications.specs._persistence.NotificationKindPersistence`
(``sa.Table`` glue).

Adding a new kind = create one ``<kind>.py`` here, append the
class to :func:`default_registry`, write the two Alembic
migrations, and (if it surfaces in REST) add a Pydantic schema
to the discriminated union in
``presentation/http/routes/notification.py``. Nothing else
needs to change.
"""

from typing import Any

from learnic.application.common.notifications.kind_spec import (
    NotificationKindRegistry,
    NotificationKindSpec,
)
from learnic.infrastructure.notifications.specs.access_revoked import (
    AccessRevokedSpec,
)
from learnic.infrastructure.notifications.specs.invite_accepted import (
    InviteAcceptedSpec,
)
from learnic.infrastructure.notifications.specs.invite_declined import (
    InviteDeclinedSpec,
)
from learnic.infrastructure.notifications.specs.invite_sent import (
    InviteSentSpec,
)
from learnic.infrastructure.notifications.specs.new_login import (
    NewLoginSpec,
)
from learnic.infrastructure.notifications.specs.storage_quota_enforced import (
    StorageQuotaEnforcedSpec,
)
from learnic.infrastructure.notifications.specs.storage_quota_warning import (
    StorageQuotaWarningSpec,
)


def default_registry() -> NotificationKindRegistry:
    """Build the registry containing every notification kind shipped today."""
    specs: list[NotificationKindSpec[Any, Any]] = [
        InviteSentSpec(),
        InviteAcceptedSpec(),
        InviteDeclinedSpec(),
        AccessRevokedSpec(),
        NewLoginSpec(),
        StorageQuotaWarningSpec(),
        StorageQuotaEnforcedSpec(),
    ]
    return NotificationKindRegistry(specs)


__all__ = [
    "AccessRevokedSpec",
    "InviteAcceptedSpec",
    "InviteDeclinedSpec",
    "InviteSentSpec",
    "NewLoginSpec",
    "StorageQuotaEnforcedSpec",
    "StorageQuotaWarningSpec",
    "default_registry",
]

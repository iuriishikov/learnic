"""Persistence half of the per-kind spec.

The application-layer Protocol
(:class:`learnic.application.common.notifications.kind_spec.NotificationKindSpec`)
covers domain glue + Redis transport + WS wire format. SQLAlchemy
cannot leak into application, so the parts that touch
``sa.Table`` live here.

Concrete classes in ``specs/<kind>.py`` implement *both* this
Protocol and ``NotificationKindSpec`` simultaneously — one object
per kind, registered once in :mod:`learnic.ioc` via
:func:`default_registry`.
"""

from collections.abc import Sequence
from typing import Any, ClassVar, Protocol, TypeVar

import sqlalchemy as sa

from learnic.entities.notification.details import NotificationDetails
from learnic.entities.notification.enums import NotificationKind
from learnic.entities.notification.models import Notification

D = TypeVar("D", bound=NotificationDetails)


class NotificationKindPersistence(Protocol[D]):
    """SA Core glue for inserting / loading a kind's subtype row.

    Pairs with :class:`NotificationKindSpec` — together they cover
    everything that varies between notification kinds.
    """

    kind: ClassVar[NotificationKind]
    table: ClassVar[sa.Table]

    def insert_values(
        self,
        notification: Notification,
        details: D,
    ) -> dict[str, Any]:
        """Build the ``INSERT`` payload for the subtype row.

        Includes ``notification_id`` and ``kind`` (the composite
        FK) plus every kind-specific column.
        """
        ...

    def load_columns(self) -> Sequence[sa.ColumnElement[Any]]:
        """Columns to ``SELECT`` from the subtype table for hydration."""
        ...

    def row_to_details(self, row: sa.Row[Any]) -> D:
        """Reconstruct the :class:`NotificationDetails` from a loaded row."""
        ...

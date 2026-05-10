from typing import Protocol

from learnic.entities.cohort.ids import WebinarScheduleID
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


class TaskScheduler(Protocol):
    """Enqueues background tasks from command handlers.

    Application handlers depend on this protocol to schedule work
    for later execution without knowing about the broker.
    Add one method per domain operation you need to enqueue.
    """

    async def schedule_example(self, payload: str) -> None: ...

    async def schedule_materialize_webinar_schedule(
        self,
        schedule_id: WebinarScheduleID,
    ) -> None:
        """Enqueue materialization of upcoming webinar sessions.

        The worker loads ``WebinarSchedule(schedule_id)``, picks up
        the cursor (max ``original_starts_at`` already materialised),
        expands the rrule and writes the next batch of
        :class:`WebinarSession` rows.

        Idempotent: re-enqueueing on an already up-to-date schedule
        produces no new sessions thanks to the
        ``UNIQUE(schedule_id, original_starts_at)`` constraint and
        the cursor.
        """
        ...

    async def schedule_send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
    ) -> None:
        """Enqueue an ad-hoc HTML email for async delivery.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html: Rendered HTML body.
            text: Optional plain-text alternative.
        """
        ...

    async def schedule_send_verification_email(
        self,
        to: str,
        raw_token: str,
    ) -> None:
        """Enqueue delivery of an email-verification link.

        Args:
            to: Recipient email address.
            raw_token: Single-use token; the worker builds the verify
                URL from the configured frontend base URL.
        """
        ...

    async def schedule_send_password_reset_email(
        self,
        to: str,
        raw_token: str,
    ) -> None:
        """Enqueue delivery of a password-reset link.

        Args:
            to: Recipient email address.
            raw_token: Single-use token; the worker builds the reset URL
                from the configured frontend base URL.
        """
        ...

    async def schedule_send_collaboration_invite_email(
        self,
        to: str,
        product_id: ProductID,
        collaboration_id: ProductCollaborationID,
        raw_token: str,
    ) -> None:
        """Send the collaboration invite link to ``to``.

        The worker builds a URL of the shape
        ``{frontend}/products/{product_id}/collaboration-invitation/
        {collaboration_id}/accept?token={raw_token}`` so the SPA
        can route to the accept page; if the user is not signed in
        the SPA bounces through ``/login?next=...``.
        """
        ...

    async def schedule_send_collaboration_accepted_email(
        self,
        to: str,
        product_id: ProductID,
        collaborator_id: UserID,
    ) -> None:
        """Notify the inviter that an invite was accepted."""
        ...

    async def schedule_send_collaboration_revoked_email(
        self,
        to: str,
        product_id: ProductID,
    ) -> None:
        """Notify a collaborator that their access was revoked."""
        ...

    async def schedule_send_collaboration_grants_updated_email(
        self,
        to: str,
        product_id: ProductID,
    ) -> None:
        """Notify a collaborator that their grants changed."""
        ...

    async def schedule_send_collaboration_left_email(
        self,
        to: str,
        product_id: ProductID,
        collaborator_id: UserID,
    ) -> None:
        """Notify the product owner that a collaborator left."""
        ...

    async def schedule_send_web_push(
        self,
        *,
        user_id: UserID,
        title: str,
        body: str,
        url: str | None = None,
        tag: str | None = None,
        icon: str | None = None,
        category: str | None = None,
        bypass_preferences: bool = False,
    ) -> None:
        """Enqueue a Web Push fanout to every subscription of ``user_id``.

        Args:
            user_id: Recipient user.
            title: System banner title.
            body: System banner body text.
            url: Optional click target opened by the SW.
            tag: Optional notification tag for in-place replacement.
            icon: Optional icon URL.
            category: :class:`NotificationCategory` value used for
                preference enforcement at the worker; ``None`` skips
                the check (system / ops broadcasts).
            bypass_preferences: ``True`` for the manual "Send test"
                path — the worker delivers regardless of the
                per-category opt-in.
        """
        ...

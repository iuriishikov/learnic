from collections.abc import Sequence
from typing import Protocol

from learnic.application.common.email.components import EmailComponent
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID


class TaskScheduler(Protocol):
    """Enqueues background tasks from command handlers.

    Application handlers depend on this protocol to schedule work
    for later execution without knowing about the broker.
    Add one method per domain operation you need to enqueue.
    """

    async def schedule_example(self, payload: str) -> None: ...

    async def schedule_purge_file_from_storage(
        self,
        file_id: FileID,
        attempt: int = 0,
        *,
        force_release_pinned: bool = False,
    ) -> None:
        """Enqueue physical removal of a soft-deleted file's S3 object.

        Called right after :meth:`File.mark_deleted` flips
        ``deleted_at``. The task re-reads the file inside the worker;
        if it sees the row still live (the producer hasn't committed
        the soft-delete yet, or rolled back) it re-enqueues itself a
        bounded number of times until the commit lands, so the
        sequence "schedule then commit" never orphans the blob and
        "schedule then rollback" never deletes a live file.

        The blob is hard-deleted along with the ``files`` row by the
        worker. Note the FK shapes the worker relies on: single-file
        and video-file blocks (draft and blog) reference the file
        with ``ON DELETE CASCADE`` — they are dropped with the file;
        photo-collage items and note-release mirror rows use
        ``ON DELETE SET NULL`` — the worker excises the draft items
        explicitly and the release mirrors degrade to a placeholder.

        Args:
            file_id: Target file's ``FileID``.
            attempt: Re-enqueue counter; callers leave it at ``0``.
                The worker increments it on each "still live" retry.
            force_release_pinned: When ``True``, the worker skips its
                defensive ``is_referenced_by_release`` re-check and
                purges even a release-pinned blob. Set only by the
                over-quota reconcile job, which deliberately evicts
                release media (quota wins over release immutability);
                the soft-delete producer already decided the eviction.
        """
        ...

    async def schedule_reconcile_storage_quotas(self) -> None:
        """Enqueue the periodic over-quota reconciliation pass.

        Triggered by an external scheduler (Kubernetes CronJob,
        host cron, etc.) — TaskIQ has no built-in cron and we keep
        the scheduling concern outside the application code on
        purpose. The worker runs
        :class:`ReconcileStorageQuotasCommandHandler` end-to-end.

        Cadence is a deployment knob (typically daily). The handler
        itself is idempotent and side-effect-bounded: it never
        re-notifies inside the cooldown and never re-enforces a
        breach that no longer exists.
        """
        ...

    async def schedule_send_email(
        self,
        to: str,
        subject: str,
        components: Sequence[EmailComponent],
    ) -> None:
        """Enqueue an email built from typed body components.

        Every transactional email — verification, password reset,
        collaboration flows, in-app notification fanout — goes through
        this single method. Callers describe the body as a list of
        :class:`EmailComponent` instances; the scheduler implementation
        renders them into HTML + plain-text alternative before handing
        the result to :class:`EmailSender` via the worker.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            components: Ordered body of the email — typed components
                rendered into the branded base layout.
        """
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

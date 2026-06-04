from typing import Protocol

from learnic.entities.note_release.models import NoteRelease


class NoteDraftResetter(Protocol):
    """Reverse of :class:`NoteReleaseSnapshotter` — restores draft from a release.

    Wipes the current draft (modules, lessons, blocks + child rows)
    of ``release.product_id`` and rehydrates it from the snapshot
    rows pinned to ``release.oid``. Fresh UUIDs are generated for
    every restored row so draft ids never collide with snapshot
    ids that may already be referenced from elsewhere (e.g. from a
    different release's ``source_*_id`` hint).

    The implementation runs entirely in the request transaction —
    callers commit or roll back as part of their own flow.
    """

    async def reset(self, release: NoteRelease) -> None: ...

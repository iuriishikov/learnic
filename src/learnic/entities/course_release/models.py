import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.course_release.value_objects import (
    CourseReleaseVersion,
    ReleaseNotes,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass
class CourseRelease(BaseEntity[CourseReleaseID]):
    """Immutable snapshot pointer for a course product.

    A release captures (via separate snapshot tables) the full
    contents of the course's draft at the moment of release.
    The entity itself records metadata: monotonic ``ordinal``,
    semver ``version``, the ``kind`` of bump, optional ``notes``,
    and audit fields.

    The actual snapshot content (modules / lessons / blocks) is
    materialized into ``course_release_*`` tables by the
    :class:`CourseReleaseSnapshotter` adapter outside this entity.
    """

    product_id: ProductID
    ordinal: int
    version: CourseReleaseVersion
    kind: CourseReleaseKind
    released_at: datetime
    released_by: UserID
    notes: ReleaseNotes | None = None

    @classmethod
    def create(
        cls,
        product_id: ProductID,
        ordinal: int,
        previous_version: CourseReleaseVersion | None,
        kind: CourseReleaseKind,
        released_by: UserID,
        notes: ReleaseNotes | None = None,
    ) -> Self:
        """Build the next release from the previous version + bump kind.

        ``previous_version=None`` means there are no prior releases:
        the implicit baseline is ``v0.0.0``, so ``patch`` →
        ``v0.0.1``, ``minor`` → ``v0.1.0``, ``major`` → ``v1.0.0``.
        """
        base = previous_version or CourseReleaseVersion.initial()
        return cls(
            oid=CourseReleaseID(uuid.uuid4()),
            product_id=product_id,
            ordinal=ordinal,
            version=base.bumped(kind),
            kind=kind,
            released_at=datetime.now(timezone.utc),
            released_by=released_by,
            notes=notes,
        )

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, assert_never

from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.models import (
    CodeBlock,
    HtmlBlock,
    KatexBlock,
    LessonBlock,
    RutubeVideoBlock,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_module.models import CourseModule
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


class ContentEventKind(StrEnum):
    """Discriminator for collaborative content events.

    Events are coarse-grained — one per domain mutation, not per
    keystroke. Clients receive a ``payload`` rich enough to apply
    the change in place via ``setQueryData`` / equivalent, without
    a REST refetch. Container-shaped events (``*_added``,
    ``block_updated``) carry a full snapshot of the affected entity
    in the same shape the REST draft endpoint returns.
    """

    MODULE_ADDED = "module_added"
    MODULE_RENAMED = "module_renamed"
    MODULE_DESCRIPTION_UPDATED = "module_description_updated"
    MODULES_REORDERED = "modules_reordered"
    MODULE_DELETED = "module_deleted"

    LESSON_ADDED = "lesson_added"
    LESSON_RENAMED = "lesson_renamed"
    LESSON_MOVED = "lesson_moved"
    LESSONS_REORDERED = "lessons_reordered"
    LESSON_DELETED = "lesson_deleted"

    BLOCK_ADDED = "block_added"
    BLOCK_UPDATED = "block_updated"
    BLOCK_DELETED = "block_deleted"
    BLOCKS_REORDERED = "blocks_reordered"

    RELEASE_CREATED = "release_created"
    DRAFT_RESET = "draft_reset"


@dataclass(slots=True, frozen=True)
class ContentEvent:
    """A single collaborative-edit event for a course product.

    Each ``payload`` carries the post-mutation state of the affected
    entity directly so clients can apply the change in place without
    a REST round-trip. Container events (``module_added`` /
    ``lesson_added`` / ``block_added`` / ``block_updated``) carry a
    full snapshot of the new/changed entity in the same shape the
    REST draft endpoint returns; trivial ones (``*_renamed``,
    ``*_reordered``, ``*_deleted``) carry only the ids and the new
    field value(s) needed to patch the cache.
    """

    kind: ContentEventKind
    product_id: ProductID
    actor_id: UserID
    payload: dict[str, Any]
    occurred_at: datetime


# Mirror of `presentation/http/routes/course_content._rutube_embed_url`.
# The template is duplicated (one f-string per layer) to keep
# `application/` independent of `presentation/`. If Rutube ever
# changes the path, both call sites must be updated together — the
# REST projection (`RutubeVideoBlockSchema.from_view`) and this
# builder.
_RUTUBE_EMBED_URL_TEMPLATE = "https://rutube.ru/play/embed/{external_id}/"


def _block_payload(block: LessonBlock) -> dict[str, Any]:
    """Serialize a draft block into the wire shape the SPA expects.

    Mirrors `presentation/http/routes/course_content.LessonBlockSchema`
    — same field names, same discriminator (`type`), same encoding
    of nullable fields. Kept in `application/` so handlers can build
    the event payload without crossing into `presentation/`.
    """
    if isinstance(block, HtmlBlock):
        return {
            "type": BlockType.HTML.value,
            "oid": str(block.oid),
            "position": block.position,
            "html": block.html.value,
        }
    if isinstance(block, KatexBlock):
        return {
            "type": BlockType.KATEX.value,
            "oid": str(block.oid),
            "position": block.position,
            "source": block.source.value,
        }
    if isinstance(block, RutubeVideoBlock):
        external_id = block.external_id.value
        return {
            "type": BlockType.RUTUBE_VIDEO.value,
            "oid": str(block.oid),
            "position": block.position,
            "external_id": external_id,
            "embed_url": _RUTUBE_EMBED_URL_TEMPLATE.format(
                external_id=external_id,
            ),
            "title": block.title.value if block.title is not None else None,
        }
    if isinstance(block, CodeBlock):
        return {
            "type": BlockType.CODE.value,
            "oid": str(block.oid),
            "position": block.position,
            "tabs": [
                {
                    "label": tab.label.value,
                    "source": tab.source.value,
                    "language": tab.language.value,
                }
                for tab in block.tabs
            ],
        }
    assert_never(block)


def block_added_payload(
    *,
    lesson_id: CourseLessonID,
    block: LessonBlock,
) -> dict[str, Any]:
    """Payload for ``BLOCK_ADDED``: parent lesson id + full block snapshot."""
    return {
        "lesson_id": str(lesson_id),
        "block": _block_payload(block),
    }


def block_updated_payload(block: LessonBlock) -> dict[str, Any]:
    """Payload for ``BLOCK_UPDATED``: full post-mutation block snapshot."""
    return {"block": _block_payload(block)}


def lesson_added_payload(
    *,
    module_id: CourseModuleID,
    lesson: CourseLesson,
) -> dict[str, Any]:
    """Payload for ``LESSON_ADDED``: parent module id + full lesson snapshot.

    Freshly-added lessons always have an empty ``blocks`` list; the
    snapshot exposes that explicitly so the SPA can splice the new
    lesson into its draft cache without a follow-up GET.
    """
    return {
        "module_id": str(module_id),
        "lesson": {
            "oid": str(lesson.oid),
            "title": lesson.title.value,
            "position": lesson.position,
            "blocks": [],
        },
    }


def lesson_moved_payload(
    *,
    lesson_id: CourseLessonID,
    from_module_id: CourseModuleID,
    to_module_id: CourseModuleID,
    position: int,
) -> dict[str, Any]:
    """Payload for ``LESSON_MOVED``: source + target module ids + new position.

    ``from_module_id`` is the lesson's module id BEFORE the move —
    it lets the SPA locate the lesson in its draft cache without
    a full tree scan.
    """
    return {
        "lesson_id": str(lesson_id),
        "from_module_id": str(from_module_id),
        "to_module_id": str(to_module_id),
        "position": position,
    }


def module_added_payload(module: CourseModule) -> dict[str, Any]:
    """Payload for ``MODULE_ADDED``: full module snapshot.

    Freshly-added modules always have an empty ``lessons`` list; the
    snapshot exposes that explicitly so the SPA can splice the new
    module into its draft cache without a follow-up GET.
    """
    return {
        "module": {
            "oid": str(module.oid),
            "title": module.title.value,
            "description": (
                module.description.value if module.description is not None else None
            ),
            "position": module.position,
            "lessons": [],
        },
    }

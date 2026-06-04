import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.value_objects import LessonTitle
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.product.ids import ProductID


@dataclass
class NoteLesson(BaseEntity[NoteLessonID]):
    """A draft lesson inside a note module.

    ``product_id`` is denormalised from the parent module so
    ownership checks read the lesson row alone (no extra JOIN).
    Move-between-modules within the same note is allowed
    (preserves ``product_id``); cross-note moves are not — they
    would invalidate the denorm.
    """

    module_id: NoteModuleID
    product_id: ProductID
    title: LessonTitle
    position: int
    created_at: datetime
    updated_at: datetime

    def rename(self, new_title: LessonTitle) -> None:
        self.title = new_title

    def move_to_module(
        self,
        new_module_id: NoteModuleID,
        new_position: int,
    ) -> None:
        self.module_id = new_module_id
        self.position = new_position

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        module_id: NoteModuleID,
        product_id: ProductID,
        title: LessonTitle,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=NoteLessonID(uuid.uuid4()),
            module_id=module_id,
            product_id=product_id,
            title=title,
            position=position,
            created_at=now,
            updated_at=now,
        )

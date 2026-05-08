import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.value_objects import LessonTitle
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID


@dataclass
class CourseLesson(BaseEntity[CourseLessonID]):
    """A draft lesson inside a course module.

    ``product_id`` is denormalised from the parent module so
    ownership checks read the lesson row alone (no extra JOIN).
    Move-between-modules within the same course is allowed
    (preserves ``product_id``); cross-course moves are not — they
    would invalidate the denorm.
    """

    module_id: CourseModuleID
    product_id: ProductID
    title: LessonTitle
    position: int
    created_at: datetime
    updated_at: datetime

    def rename(self, new_title: LessonTitle) -> None:
        self.title = new_title

    def move_to_module(
        self,
        new_module_id: CourseModuleID,
        new_position: int,
    ) -> None:
        self.module_id = new_module_id
        self.position = new_position

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        module_id: CourseModuleID,
        product_id: ProductID,
        title: LessonTitle,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=CourseLessonID(uuid.uuid4()),
            module_id=module_id,
            product_id=product_id,
            title=title,
            position=position,
            created_at=now,
            updated_at=now,
        )

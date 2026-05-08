import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_module.value_objects import (
    ModuleDescription,
    ModuleTitle,
)
from learnic.entities.product.ids import ProductID


@dataclass
class CourseModule(BaseEntity[CourseModuleID]):
    """A draft module inside a course product.

    Lives only in the draft workspace — releases snapshot it into a
    parallel ``course_release_modules`` table at release time.
    Authors mutate this aggregate freely; students never see it
    directly (they read pinned-release content instead).
    """

    product_id: ProductID
    title: ModuleTitle
    position: int
    created_at: datetime
    updated_at: datetime
    description: ModuleDescription | None = None

    def rename(self, new_title: ModuleTitle) -> None:
        self.title = new_title

    def update_description(
        self,
        new_description: ModuleDescription | None,
    ) -> None:
        self.description = new_description

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        product_id: ProductID,
        title: ModuleTitle,
        position: int,
        description: ModuleDescription | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=CourseModuleID(uuid.uuid4()),
            product_id=product_id,
            title=title,
            description=description,
            position=position,
            created_at=now,
            updated_at=now,
        )

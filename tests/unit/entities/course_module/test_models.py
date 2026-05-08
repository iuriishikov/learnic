import uuid

from learnic.entities.course_module.models import CourseModule
from learnic.entities.course_module.value_objects import (
    ModuleDescription,
    ModuleTitle,
)
from learnic.entities.product.ids import ProductID


def _product_id() -> ProductID:
    return ProductID(uuid.uuid4())


class TestCreate:
    def test_initial_state(self) -> None:
        m = CourseModule.create(
            product_id=_product_id(),
            title=ModuleTitle("Intro"),
            position=0,
        )
        assert m.title.value == "Intro"
        assert m.position == 0
        assert m.description is None

    def test_with_description(self) -> None:
        m = CourseModule.create(
            product_id=_product_id(),
            title=ModuleTitle("Intro"),
            position=0,
            description=ModuleDescription("d"),
        )
        assert m.description is not None
        assert m.description.value == "d"

    def test_unique_oids(self) -> None:
        a = CourseModule.create(
            product_id=_product_id(),
            title=ModuleTitle("A"),
            position=0,
        )
        b = CourseModule.create(
            product_id=_product_id(),
            title=ModuleTitle("B"),
            position=1,
        )
        assert a.oid != b.oid


class TestMutators:
    def test_rename(self) -> None:
        m = CourseModule.create(
            product_id=_product_id(),
            title=ModuleTitle("Old"),
            position=0,
        )
        m.rename(ModuleTitle("New"))
        assert m.title.value == "New"

    def test_update_description_set_then_clear(self) -> None:
        m = CourseModule.create(
            product_id=_product_id(),
            title=ModuleTitle("Mod"),
            position=0,
        )
        m.update_description(ModuleDescription("d"))
        assert m.description is not None
        m.update_description(None)
        assert m.description is None

    def test_change_position(self) -> None:
        m = CourseModule.create(
            product_id=_product_id(),
            title=ModuleTitle("M"),
            position=0,
        )
        m.change_position(5)
        assert m.position == 5

import pytest

from learnic.entities.course_module.constants import (
    MODULE_DESCRIPTION_MAX_LEN,
    MODULE_TITLE_MAX_LEN,
)
from learnic.entities.course_module.errors import (
    CourseModuleFieldTooLongError,
    EmptyCourseModuleFieldError,
)
from learnic.entities.course_module.value_objects import (
    ModuleDescription,
    ModuleTitle,
)


class TestModuleTitle:
    def test_accepts_valid(self) -> None:
        assert ModuleTitle("Введение").value == "Введение"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyCourseModuleFieldError) as exc:
            ModuleTitle("   ")
        assert exc.value.field == "title"

    def test_rejects_too_long(self) -> None:
        with pytest.raises(CourseModuleFieldTooLongError):
            ModuleTitle("x" * (MODULE_TITLE_MAX_LEN + 1))


class TestModuleDescription:
    def test_accepts_valid(self) -> None:
        assert ModuleDescription("Описание").value == "Описание"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyCourseModuleFieldError):
            ModuleDescription("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(CourseModuleFieldTooLongError):
            ModuleDescription("x" * (MODULE_DESCRIPTION_MAX_LEN + 1))

    def test_of_optional_returns_none_for_none(self) -> None:
        assert ModuleDescription.of_optional(None) is None

    def test_of_optional_returns_vo_for_value(self) -> None:
        result = ModuleDescription.of_optional("Hi")
        assert result is not None
        assert result.value == "Hi"

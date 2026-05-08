from learnic.entities.common.value_object import ValueObject
from learnic.entities.course_module.constants import (
    MODULE_DESCRIPTION_MAX_LEN,
    MODULE_TITLE_MAX_LEN,
)
from learnic.entities.course_module.errors import (
    CourseModuleFieldTooLongError,
    EmptyCourseModuleFieldError,
)


class ModuleTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyCourseModuleFieldError("title")
        if len(self.value) > MODULE_TITLE_MAX_LEN:
            raise CourseModuleFieldTooLongError(
                "title",
                MODULE_TITLE_MAX_LEN,
            )


class ModuleDescription(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyCourseModuleFieldError("description")
        if len(self.value) > MODULE_DESCRIPTION_MAX_LEN:
            raise CourseModuleFieldTooLongError(
                "description",
                MODULE_DESCRIPTION_MAX_LEN,
            )

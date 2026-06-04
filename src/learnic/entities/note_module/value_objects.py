from learnic.entities.common.value_object import ValueObject
from learnic.entities.note_module.constants import (
    MODULE_DESCRIPTION_MAX_LEN,
    MODULE_TITLE_MAX_LEN,
)
from learnic.entities.note_module.errors import (
    NoteModuleFieldTooLongError,
    EmptyNoteModuleFieldError,
)


class ModuleTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNoteModuleFieldError("title")
        if len(self.value) > MODULE_TITLE_MAX_LEN:
            raise NoteModuleFieldTooLongError(
                "title",
                MODULE_TITLE_MAX_LEN,
            )


class ModuleDescription(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyNoteModuleFieldError("description")
        if len(self.value) > MODULE_DESCRIPTION_MAX_LEN:
            raise NoteModuleFieldTooLongError(
                "description",
                MODULE_DESCRIPTION_MAX_LEN,
            )

"""Shared command-input shapes for interactive-answer block handlers.

The three add / update pairs (single_choice, multi_choice,
text_input) take essentially the same shape — a list of option
candidates plus per-option ``is_correct`` flag, or a list of
accepted-answer strings. Keep the helpers in one place so the
six handlers stay thin and the conversion logic is tested once.

Ids are generated server-side: the author submits ``(label,
is_correct)`` tuples without thinking about UUIDs. Replace
semantics on update mean each update mints fresh option ids —
intentional: there are no external references to option ids,
so identity preservation across edits would add complexity
without payoff.
"""

from dataclasses import dataclass

from learnic.entities.course_block.errors import (
    EmptyCorrectOptionsError,
    MultipleCorrectOptionsInSingleChoiceError,
)
from learnic.entities.course_block.ids import ChoiceOptionID
from learnic.entities.course_block.models import ChoiceOption
from learnic.entities.course_block.value_objects import ChoiceOptionLabel


@dataclass(slots=True, frozen=True)
class ChoiceOptionDraftInput:
    """One option as submitted by the author.

    ``label`` is the raw text; the VO is constructed inside the
    handler so invariants surface as ``FieldError`` subclasses.
    ``is_correct`` marks the option as a correct answer — for
    single-choice exactly one option must be flagged, for
    multi-choice at least one.
    """

    label: str
    is_correct: bool


def _build_options(
    inputs: tuple[ChoiceOptionDraftInput, ...],
) -> list[ChoiceOption]:
    """Mint fresh ``ChoiceOption`` entities, one per input row."""
    return [
        ChoiceOption.create(ChoiceOptionLabel(o.label)) for o in inputs
    ]


def options_with_single_correct(
    inputs: tuple[ChoiceOptionDraftInput, ...],
) -> tuple[list[ChoiceOption], ChoiceOptionID]:
    """Convert author input into ``(options, correct_option_id)``.

    Raises:
        EmptyCorrectOptionsError: No option was flagged correct.
        MultipleCorrectOptionsInSingleChoiceError: More than one
            option was flagged correct (the caller should switch
            to multi-choice instead).
    """
    correct_count = sum(1 for o in inputs if o.is_correct)
    if correct_count == 0:
        raise EmptyCorrectOptionsError()
    if correct_count > 1:
        raise MultipleCorrectOptionsInSingleChoiceError(correct_count)
    options = _build_options(inputs)
    # ``zip`` keeps positional pairing intact — the i-th option
    # carries the i-th input's flag. Picking the single ``True``
    # one is unambiguous.
    correct_id = next(
        opt.oid for opt, src in zip(options, inputs, strict=True) if src.is_correct
    )
    return options, correct_id


def options_with_multi_correct(
    inputs: tuple[ChoiceOptionDraftInput, ...],
) -> tuple[list[ChoiceOption], frozenset[ChoiceOptionID]]:
    """Convert author input into ``(options, correct_option_ids)``.

    Raises:
        EmptyCorrectOptionsError: No option was flagged correct.
    """
    if not any(o.is_correct for o in inputs):
        raise EmptyCorrectOptionsError()
    options = _build_options(inputs)
    correct_ids = frozenset(
        opt.oid for opt, src in zip(options, inputs, strict=True) if src.is_correct
    )
    return options, correct_ids

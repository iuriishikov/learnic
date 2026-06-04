"""Per-product-kind enrollment policies (strategy pattern).

Currently only the ``NOTE`` strategy exists. The shape is
preserved so additional enrollment kinds can be added later by
declaring a new :class:`EnrollmentTarget` variant, an
:class:`EnrollmentStrategy` impl, and an entry in the
``EnrollmentStrategiesProvider`` in ``ioc.py``.
"""

from dataclasses import dataclass
from typing import ClassVar, Final, Protocol, TypeAlias
from uuid import UUID

from learnic.entities.enrollment.enums import EnrollmentKind
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class NoteEnrollmentTarget:
    """Note-kind enrollment target. Ties to a note product."""

    enrollment_kind: ClassVar[EnrollmentKind] = EnrollmentKind.NOTE
    product_id: ProductID

    @property
    def parent_id(self) -> UUID:
        return self.product_id


EnrollmentTarget: TypeAlias = NoteEnrollmentTarget


class EnrollmentStrategy(Protocol):
    """Per-product-kind enrollment policy."""

    enrollment_kind: ClassVar[EnrollmentKind]

    async def find_existing(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment | None:
        """Return the existing enrollment if the student is already
        enrolled in this target, else ``None``.
        """
        ...

    async def enroll(
        self,
        student_id: UserID,
        target: EnrollmentTarget,
    ) -> Enrollment:
        """Validate kind-specific pre-conditions, construct the
        :class:`Enrollment` and register it with the unit of work.
        """
        ...


# Fail-fast contract. Whenever a new ``EnrollmentKind`` is added,
# its strategy must also be declared here.
_DECLARED_STRATEGIES: Final[frozenset[EnrollmentKind]] = frozenset(
    {
        EnrollmentKind.NOTE,
    },
)


def _check_contract() -> None:
    missing = set(EnrollmentKind) - _DECLARED_STRATEGIES
    if missing:
        raise RuntimeError(
            "EnrollmentStrategy contract incomplete; add a strategy "
            "for: "
            f"{sorted(k.value for k in missing)}",
        )


_check_contract()

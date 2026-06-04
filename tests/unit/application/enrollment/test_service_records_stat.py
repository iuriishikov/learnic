import uuid
from unittest.mock import AsyncMock, MagicMock

from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.enrollment.strategies import (
    NoteEnrollmentTarget,
)
from learnic.entities.enrollment.enums import EnrollmentKind
from learnic.entities.product.ids import ProductID
from learnic.entities.statistic.enums import StatisticType
from learnic.entities.user.models import UserID


async def test_enroll_records_enrollment_statistic() -> None:
    student_id = UserID(uuid.uuid4())
    product_id = ProductID(uuid.uuid4())

    enrollment = MagicMock()
    enrollment.oid = uuid.uuid4()
    strategy = AsyncMock()
    strategy.find_existing = AsyncMock(return_value=None)
    strategy.enroll = AsyncMock(return_value=enrollment)
    transaction = AsyncMock()
    statistics = AsyncMock()

    service = EnrollmentService(
        strategies={EnrollmentKind.NOTE: strategy},
        transaction=transaction,
        statistics=statistics,
    )
    await service.enroll(
        student_id=student_id,
        target=NoteEnrollmentTarget(product_id=product_id),
    )

    transaction.commit.assert_awaited_once()
    statistics.record.assert_awaited_once()
    recorded = statistics.record.await_args.args[0]
    assert recorded.type is StatisticType.ENROLLMENT
    assert recorded.actor_id == student_id
    assert recorded.details.product_id == product_id

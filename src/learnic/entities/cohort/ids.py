import uuid
from typing import NewType

CohortID = NewType("CohortID", uuid.UUID)
WebinarScheduleID = NewType("WebinarScheduleID", uuid.UUID)
WebinarSessionID = NewType("WebinarSessionID", uuid.UUID)

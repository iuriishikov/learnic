import uuid
from typing import NewType

PushSubscriptionID = NewType("PushSubscriptionID", uuid.UUID)

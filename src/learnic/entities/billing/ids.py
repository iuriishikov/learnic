import uuid
from typing import NewType

SubscriptionID = NewType("SubscriptionID", uuid.UUID)
StorageQuotaBreachID = NewType("StorageQuotaBreachID", uuid.UUID)

# Plan code is a short uppercase token ("FREE", "BETA", ...) — kept
# as a stand-alone newtype on top of ``str`` so the persistence
# layer and the registry agree on shape without conflating it with
# arbitrary strings.
PlanCode = NewType("PlanCode", str)

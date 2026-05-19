import uuid
from typing import NewType

OrderID = NewType("OrderID", uuid.UUID)

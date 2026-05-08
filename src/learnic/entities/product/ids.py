import uuid
from typing import NewType

ProductID = NewType("ProductID", uuid.UUID)
ProductQAID = NewType("ProductQAID", uuid.UUID)

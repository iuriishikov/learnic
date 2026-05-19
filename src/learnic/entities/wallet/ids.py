import uuid
from typing import NewType

WalletID = NewType("WalletID", uuid.UUID)
FreezeEntryID = NewType("FreezeEntryID", uuid.UUID)
LedgerEntryID = NewType("LedgerEntryID", uuid.UUID)

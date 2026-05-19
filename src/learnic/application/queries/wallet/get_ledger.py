from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.wallet import (
    LedgerEntryView,
    LedgerReader,
    WalletReader,
)
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.errors import WalletNotFoundError


@dataclass(slots=True, frozen=True)
class GetWalletLedgerQuery:
    user_id: UserID
    currency: Currency
    pagination: Pagination


@final
class GetWalletLedgerQueryHandler:
    def __init__(
        self,
        wallet_reader: WalletReader,
        ledger_reader: LedgerReader,
    ) -> None:
        self._wallet_reader: Final = wallet_reader
        self._ledger_reader: Final = ledger_reader

    async def run(self, data: GetWalletLedgerQuery) -> list[LedgerEntryView]:
        wallet = await self._wallet_reader.for_user(
            data.user_id,
            data.currency,
        )
        if wallet is None:
            raise WalletNotFoundError
        return await self._ledger_reader.paginated_for_wallet(
            wallet.oid,
            data.pagination,
        )

from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.wallet import (
    WalletReader,
    WalletView,
)
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.errors import WalletNotFoundError


@dataclass(slots=True, frozen=True)
class GetWalletQuery:
    user_id: UserID
    currency: Currency


@final
class GetWalletQueryHandler:
    def __init__(self, reader: WalletReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetWalletQuery) -> WalletView:
        view = await self._reader.for_user(data.user_id, data.currency)
        if view is None:
            raise WalletNotFoundError
        return view

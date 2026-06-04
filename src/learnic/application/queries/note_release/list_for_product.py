from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_release import (
    NoteReleaseReader,
    NoteReleaseSummaryView,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.entities.product.capabilities import ProductCapability
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListNoteReleasesQuery:
    actor_id: UserID
    product_id: ProductID


@final
class ListNoteReleasesQueryHandler:
    """Return all releases of a note, newest first.

    Caller needs ``READ_PRODUCT`` on the target product, so the
    owner and any collaborator with that permission (Editor,
    Commentor, custom roles) can list releases.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        release_reader: NoteReleaseReader,
    ) -> None:
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._release_reader: Final = release_reader

    async def run(
        self,
        data: ListNoteReleasesQuery,
    ) -> list[NoteReleaseSummaryView]:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.READ_PRODUCT,
        )
        product.require_supports(ProductCapability.HAS_NOTE_RELEASES)
        return await self._release_reader.list_for_product(data.product_id)

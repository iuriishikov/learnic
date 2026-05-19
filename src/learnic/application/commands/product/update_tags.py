from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import (
    Authorizer,
    AuthzTarget,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.tag import (
    ProductTagsSaver,
    TagGateway,
)
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.product_events import (
    ProductEventBus,
    TagsChangedPayload,
    publish_product_event,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.tag.constants import PRODUCT_TAGS_MAX
from learnic.entities.tag.errors import TooManyTagsError
from learnic.entities.tag.ids import TagID
from learnic.entities.tag.models import Tag
from learnic.entities.tag.value_objects import TagColor, TagName, TagSlug
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ExistingTagSpec:
    """Reference to a tag that already exists in the global pool."""

    tag_id: TagID


@dataclass(slots=True, frozen=True)
class NewTagSpec:
    """Get-or-create directive for a tag the SPA could not match locally.

    The handler still tries to find an existing tag by slug before
    inserting — two clients typing the same tag at the same moment
    converge on a single row instead of racing into a unique-index
    conflict.
    """

    name: str
    color: str


TagSpec = ExistingTagSpec | NewTagSpec


@dataclass(slots=True, frozen=True)
class UpdateProductTagsCommand:
    actor_id: UserID
    product_id: ProductID
    specs: list[TagSpec]


@final
class UpdateProductTagsCommandHandler:
    """PUT-style replace of a product's tag list with get-or-create.

    Accepts a mixed list of existing-by-id and new-by-name specs,
    materializes them into tags (creating missing ones on the fly),
    rewrites the ``product_tags`` slice in one transaction, then
    publishes a single ``tags_changed`` event. Duplicates within the
    payload are collapsed in input order — the first occurrence
    wins, later duplicates are dropped silently so the SPA does not
    have to dedupe before sending.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        entity_saver: EntitySaver,
        product_gateway: ProductGateway,
        tag_gateway: TagGateway,
        product_tags_saver: ProductTagsSaver,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._entity_saver: Final = entity_saver
        self._product_gateway: Final = product_gateway
        self._tag_gateway: Final = tag_gateway
        self._product_tags_saver: Final = product_tags_saver
        self._event_bus: Final = event_bus

    async def run(self, data: UpdateProductTagsCommand) -> list[Tag]:
        if len(data.specs) > PRODUCT_TAGS_MAX:
            raise TooManyTagsError(PRODUCT_TAGS_MAX)

        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.EDIT_DESCRIPTION,
        )

        resolved: list[Tag] = []
        seen: set[TagID] = set()
        for spec in data.specs:
            tag = await self._resolve_spec(spec, actor_id=data.actor_id)
            if tag.oid in seen:
                continue
            seen.add(tag.oid)
            resolved.append(tag)

        tag_ids = [tag.oid for tag in resolved]
        # Newly-created tags were only ``session.add(...)``-ed by
        # ``_resolve_spec``; flush so their INSERTs land before the
        # ``product_tags`` rows that reference them via FK in
        # :meth:`ProductTagsSaver.replace`. Without this the FK fails
        # with ``IntegrityError`` on the new tag's id.
        await self._transaction.flush()
        await self._product_tags_saver.replace(data.product_id, tag_ids)
        await self._transaction.commit()

        await publish_product_event(
            self._event_bus,
            payload=TagsChangedPayload.of(resolved),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        return resolved

    async def _resolve_spec(
        self,
        spec: TagSpec,
        *,
        actor_id: UserID,
    ) -> Tag:
        if isinstance(spec, ExistingTagSpec):
            tag = await self._tag_gateway.with_id(spec.tag_id)
            if tag is None:
                raise EntityNotFoundError(spec.tag_id)
            return tag

        name = TagName(spec.name)
        color = TagColor(spec.color)
        slug = TagSlug.from_name(name)
        existing = await self._tag_gateway.with_slug(slug)
        if existing is not None:
            return existing
        new_tag = Tag.create(name=name, color=color, created_by=actor_id)
        self._entity_saver.add_one(new_tag)
        return new_tag

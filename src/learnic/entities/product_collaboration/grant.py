import uuid
from dataclasses import dataclass
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product_collaboration.errors import InvalidScopeError
from learnic.entities.product_collaboration.ids import CollaborationGrantID
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import ScopeType


@dataclass
class CollaborationGrant(BaseEntity[CollaborationGrantID]):
    """A scoped role assignment inside a :class:`ProductCollaboration`.

    Grants are owned by their parent collaboration aggregate —
    callers mutate them through ``ProductCollaboration`` methods
    rather than constructing or saving them directly. The ``oid``
    exists so the persistence layer can do partial updates
    (replace one grant without rewriting all of them) and so the
    write API can address an individual grant for removal.
    """

    role_id: RoleID
    scope_type: ScopeType
    scope_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if self.scope_type is ScopeType.PRODUCT:
            if self.scope_id is not None:
                raise InvalidScopeError("product_scope_must_have_null_id")
        elif self.scope_id is None:
            raise InvalidScopeError("non_product_scope_requires_id")

    def covers(
        self,
        target_type: ScopeType,
        target_id: uuid.UUID | None,
        *,
        target_module_id: uuid.UUID | None = None,
    ) -> bool:
        """Return ``True`` if this grant's scope covers the given target.

        Coverage rules:

        - ``PRODUCT`` scope covers every target inside the product.
        - ``MODULE`` scope covers itself when the target is the
          same module, and covers ``LESSON`` targets whose parent
          module matches ``target_module_id``.
        - ``LESSON`` scope covers only the exact lesson target.

        ``target_module_id`` must be provided when ``target_type``
        is ``LESSON`` so module-scope grants can match it; for
        product/module targets it is ignored.
        """
        if self.scope_type is ScopeType.PRODUCT:
            return True
        if self.scope_type is ScopeType.MODULE:
            if target_type is ScopeType.MODULE:
                return target_id == self.scope_id
            if target_type is ScopeType.LESSON:
                return target_module_id == self.scope_id
            return False
        # LESSON scope
        if target_type is ScopeType.LESSON:
            return target_id == self.scope_id
        return False

    @classmethod
    def create(
        cls,
        role_id: RoleID,
        scope_type: ScopeType,
        scope_id: uuid.UUID | None,
    ) -> Self:
        return cls(
            oid=CollaborationGrantID(uuid.uuid4()),
            role_id=role_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

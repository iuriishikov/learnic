"""Tests for the Authorizer's resolution logic.

The protocol-level :class:`Authorizer` is implemented by
:class:`AuthorizerService` in the infrastructure layer; that
implementation talks to SQL. These unit tests cover the pure-logic
fragment used by every implementation: scope coverage rules
(:func:`CollaborationGrant.covers`), permission-implication
expansion (:func:`expand_implied`), and the union/short-circuit
semantics that any conformant implementation must honour. The
infrastructure SQL adapter has its own integration test that
exercises the end-to-end path.
"""

import uuid

from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import (
    Permission,
    ScopeType,
    expand_implied,
)


def _grant(
    *,
    scope_type: ScopeType,
    scope_id: uuid.UUID | None,
) -> CollaborationGrant:
    return CollaborationGrant.create(
        role_id=RoleID(uuid.uuid4()),
        scope_type=scope_type,
        scope_id=scope_id,
    )


class TestEffectivePermissionsResolution:
    """Mirrors what ``AuthorizerService._covering_role_ids`` does."""

    def setup_method(self) -> None:
        self.module_id = uuid.uuid4()
        self.lesson_id = uuid.uuid4()
        self.role_perms: dict[RoleID, frozenset[Permission]] = {}

    def _resolve(
        self,
        grants: list[CollaborationGrant],
        target_type: ScopeType,
        target_id: uuid.UUID | None,
        *,
        target_module_id: uuid.UUID | None = None,
    ) -> frozenset[Permission]:
        covering = [
            grant
            for grant in grants
            if grant.covers(
                target_type,
                target_id,
                target_module_id=target_module_id,
            )
        ]
        union: set[Permission] = set()
        for grant in covering:
            union |= self.role_perms.get(grant.role_id, frozenset())
        return expand_implied(frozenset(union))

    def test_product_grant_grants_everywhere(self) -> None:
        grant = _grant(scope_type=ScopeType.PRODUCT, scope_id=None)
        self.role_perms[grant.role_id] = frozenset({Permission.PUBLISH})
        result = self._resolve(
            [grant],
            ScopeType.LESSON,
            self.lesson_id,
            target_module_id=self.module_id,
        )
        assert Permission.PUBLISH in result

    def test_module_grant_excludes_other_module(self) -> None:
        grant = _grant(
            scope_type=ScopeType.MODULE,
            scope_id=self.module_id,
        )
        self.role_perms[grant.role_id] = frozenset(
            {Permission.EDIT_LESSONS},
        )
        other_module = uuid.uuid4()
        result = self._resolve(
            [grant],
            ScopeType.MODULE,
            other_module,
        )
        assert Permission.EDIT_LESSONS not in result

    def test_module_grant_covers_lesson_in_same_module(self) -> None:
        grant = _grant(
            scope_type=ScopeType.MODULE,
            scope_id=self.module_id,
        )
        self.role_perms[grant.role_id] = frozenset(
            {Permission.EDIT_LESSONS},
        )
        result = self._resolve(
            [grant],
            ScopeType.LESSON,
            self.lesson_id,
            target_module_id=self.module_id,
        )
        assert Permission.EDIT_LESSONS in result

    def test_implied_permissions_are_included(self) -> None:
        grant = _grant(scope_type=ScopeType.PRODUCT, scope_id=None)
        self.role_perms[grant.role_id] = frozenset(
            {Permission.EDIT_MODULES},
        )
        result = self._resolve(
            [grant],
            ScopeType.PRODUCT,
            None,
        )
        # EDIT_MODULES → EDIT_LESSONS → READ_PRODUCT
        assert Permission.EDIT_LESSONS in result
        assert Permission.READ_PRODUCT in result

    def test_multiple_grants_union_their_permissions(self) -> None:
        product_grant = _grant(
            scope_type=ScopeType.PRODUCT,
            scope_id=None,
        )
        module_grant = _grant(
            scope_type=ScopeType.MODULE,
            scope_id=self.module_id,
        )
        self.role_perms[product_grant.role_id] = frozenset(
            {Permission.READ_PRODUCT},
        )
        self.role_perms[module_grant.role_id] = frozenset(
            {Permission.EDIT_LESSONS},
        )
        result = self._resolve(
            [product_grant, module_grant],
            ScopeType.MODULE,
            self.module_id,
        )
        assert Permission.READ_PRODUCT in result
        assert Permission.EDIT_LESSONS in result

    def test_lesson_grant_does_not_leak_to_other_lessons(self) -> None:
        grant = _grant(
            scope_type=ScopeType.LESSON,
            scope_id=self.lesson_id,
        )
        self.role_perms[grant.role_id] = frozenset(
            {Permission.EDIT_LESSONS},
        )
        other = uuid.uuid4()
        result = self._resolve(
            [grant],
            ScopeType.LESSON,
            other,
            target_module_id=self.module_id,
        )
        assert Permission.EDIT_LESSONS not in result

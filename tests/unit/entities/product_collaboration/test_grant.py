import uuid

import pytest

from learnic.entities.product_collaboration.errors import InvalidScopeError
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import ScopeType


def _role_id() -> RoleID:
    return RoleID(uuid.uuid4())


class TestGrantInvariants:
    def test_product_scope_must_have_null_id(self) -> None:
        with pytest.raises(InvalidScopeError):
            CollaborationGrant.create(
                role_id=_role_id(),
                scope_type=ScopeType.PRODUCT,
                scope_id=uuid.uuid4(),
            )

    def test_module_scope_requires_id(self) -> None:
        with pytest.raises(InvalidScopeError):
            CollaborationGrant.create(
                role_id=_role_id(),
                scope_type=ScopeType.MODULE,
                scope_id=None,
            )

    def test_lesson_scope_requires_id(self) -> None:
        with pytest.raises(InvalidScopeError):
            CollaborationGrant.create(
                role_id=_role_id(),
                scope_type=ScopeType.LESSON,
                scope_id=None,
            )


class TestGrantCovers:
    def setup_method(self) -> None:
        self.module_id = uuid.uuid4()
        self.other_module_id = uuid.uuid4()
        self.lesson_id = uuid.uuid4()
        self.other_lesson_id = uuid.uuid4()

    def _product_grant(self) -> CollaborationGrant:
        return CollaborationGrant.create(
            role_id=_role_id(),
            scope_type=ScopeType.PRODUCT,
            scope_id=None,
        )

    def _module_grant(self, module_id: uuid.UUID) -> CollaborationGrant:
        return CollaborationGrant.create(
            role_id=_role_id(),
            scope_type=ScopeType.MODULE,
            scope_id=module_id,
        )

    def _lesson_grant(self, lesson_id: uuid.UUID) -> CollaborationGrant:
        return CollaborationGrant.create(
            role_id=_role_id(),
            scope_type=ScopeType.LESSON,
            scope_id=lesson_id,
        )

    def test_product_scope_covers_everything(self) -> None:
        grant = self._product_grant()
        assert grant.covers(ScopeType.PRODUCT, None)
        assert grant.covers(ScopeType.MODULE, self.module_id)
        assert grant.covers(
            ScopeType.LESSON,
            self.lesson_id,
            target_module_id=self.module_id,
        )

    def test_module_scope_covers_self(self) -> None:
        grant = self._module_grant(self.module_id)
        assert grant.covers(ScopeType.MODULE, self.module_id)

    def test_module_scope_covers_lessons_in_same_module(self) -> None:
        grant = self._module_grant(self.module_id)
        assert grant.covers(
            ScopeType.LESSON,
            self.lesson_id,
            target_module_id=self.module_id,
        )

    def test_module_scope_does_not_cover_other_module(self) -> None:
        grant = self._module_grant(self.module_id)
        assert not grant.covers(
            ScopeType.MODULE,
            self.other_module_id,
        )

    def test_module_scope_does_not_cover_lesson_of_other_module(self) -> None:
        grant = self._module_grant(self.module_id)
        assert not grant.covers(
            ScopeType.LESSON,
            self.lesson_id,
            target_module_id=self.other_module_id,
        )

    def test_module_scope_does_not_cover_product(self) -> None:
        grant = self._module_grant(self.module_id)
        assert not grant.covers(ScopeType.PRODUCT, None)

    def test_lesson_scope_covers_only_self(self) -> None:
        grant = self._lesson_grant(self.lesson_id)
        assert grant.covers(ScopeType.LESSON, self.lesson_id)
        assert not grant.covers(
            ScopeType.LESSON,
            self.other_lesson_id,
        )
        assert not grant.covers(
            ScopeType.MODULE,
            self.module_id,
        )
        assert not grant.covers(ScopeType.PRODUCT, None)

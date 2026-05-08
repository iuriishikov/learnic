from learnic.entities.role.permissions import (
    PERMISSION_IMPLIES,
    Permission,
    expand_implied,
)


class TestExpandImplied:
    def test_singleton_with_no_implications_returns_self(self) -> None:
        result = expand_implied(frozenset({Permission.READ_PRODUCT}))
        assert result == frozenset({Permission.READ_PRODUCT})

    def test_implications_are_added(self) -> None:
        result = expand_implied(frozenset({Permission.EDIT_DESCRIPTION}))
        assert Permission.READ_PRODUCT in result
        assert Permission.EDIT_DESCRIPTION in result

    def test_transitive_closure_for_edit_modules(self) -> None:
        # EDIT_MODULES → EDIT_LESSONS → READ_PRODUCT
        result = expand_implied(frozenset({Permission.EDIT_MODULES}))
        assert Permission.EDIT_MODULES in result
        assert Permission.EDIT_LESSONS in result
        assert Permission.READ_PRODUCT in result

    def test_no_cycles_terminate(self) -> None:
        result = expand_implied(
            frozenset(
                {
                    Permission.EDIT_MODULES,
                    Permission.EDIT_LESSONS,
                    Permission.READ_PRODUCT,
                },
            ),
        )
        assert {
            Permission.EDIT_MODULES,
            Permission.EDIT_LESSONS,
            Permission.READ_PRODUCT,
        } <= result

    def test_implies_table_does_not_reference_unknown_permissions(
        self,
    ) -> None:
        all_permissions = set(Permission)
        for parent, implied in PERMISSION_IMPLIES.items():
            assert parent in all_permissions
            assert implied <= all_permissions

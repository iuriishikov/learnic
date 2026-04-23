"""Custom route class that combines dishka DI with per-route error maps."""

from typing import Any, Callable

from dishka.integrations.fastapi import inject

from fastapi_error_map.routing import ErrorAwareRoute


class DishkaErrorAwareRoute(ErrorAwareRoute):
    """``ErrorAwareRoute`` with automatic ``FromDishka`` injection.

    Combines ``fastapi-error-map``'s per-route ``error_map`` with
    dishka's ``FromDishka[...]`` auto-resolution — same ergonomics as
    ``dishka.integrations.fastapi.DishkaRoute`` but with error mapping.
    Handlers don't need ``@inject`` decorators.
    """

    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        **kwargs: Any,
    ) -> None:
        endpoint = inject(endpoint)
        super().__init__(path, endpoint, **kwargs)

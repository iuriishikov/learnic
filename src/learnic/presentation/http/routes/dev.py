"""Dev-only endpoints for local testing.

This router is registered in ``bootstrap.setup_routes`` **only when**
``AppConfig.environment == "development"``. In production the import
chain still runs (Python module load is harmless) but the router is
never attached to the FastAPI app — the routes physically do not
exist in prod, removing any risk of accidental activation by a
mis-set flag.

Currently empty after the payment/webinar removal. New dev-only
endpoints can be attached here as the domain grows.
"""

from fastapi_error_map import ErrorAwareRouter

from learnic.presentation.http.common.router import DishkaErrorAwareRoute

dev_router = ErrorAwareRouter(
    prefix="/dev",
    tags=["Dev"],
    route_class=DishkaErrorAwareRoute,
)

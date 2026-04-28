from fastapi import APIRouter, status

from learnic.presentation.http.common.schemas import (
    HealthSchema,
    WelcomeSchema,
)

router = APIRouter(tags=["Root"])


@router.get(
    "/",
    summary="Welcome banner",
    operation_id="getRoot",
    status_code=status.HTTP_200_OK,
    response_model=WelcomeSchema,
)
async def root() -> WelcomeSchema:
    """Greet the caller at the API root.

    Returns:
        :class:`WelcomeSchema` with a stable welcome message confirming
        the service is reachable.
    """
    return WelcomeSchema(message="Welcome to Learnic's API")


@router.get(
    "/healthcheck",
    summary="Liveness probe",
    operation_id="healthcheck",
    status_code=status.HTTP_200_OK,
    response_model=HealthSchema,
)
async def healthcheck() -> HealthSchema:
    """Report liveness for Docker and Caddy probes.

    Returns:
        :class:`HealthSchema` consumed by the ``HEALTHCHECK`` directive
        in ``Dockerfile`` and by Caddy's ``health_uri`` in
        ``Caddyfile``. Always ``{"status": "ok"}`` when the API
        process is up; container orchestration treats anything else
        as a failure.
    """
    return HealthSchema(status="ok")

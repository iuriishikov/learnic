from fastapi import APIRouter, status

router = APIRouter(tags=["Root"])


@router.get("/", status_code=status.HTTP_200_OK)
async def root() -> dict[str, str]:
    """Greet the caller at the API root.

    Returns:
        A welcome message confirming the service is reachable.
    """
    return {"message": "Welcome to Learnic's API"}


@router.get("/healthcheck", status_code=status.HTTP_200_OK)
async def healthcheck() -> dict[str, str]:
    """Report liveness for Docker and Caddy probes.

    Returns:
        A status indicator consumed by the ``HEALTHCHECK`` directive in
        ``Dockerfile`` and by Caddy's ``health_uri`` in ``Caddyfile``.
    """
    return {"status": "ok"}

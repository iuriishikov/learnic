# syntax=docker/dockerfile:1.7

FROM python:3.14-slim-bookworm AS builder

ENV POETRY_VERSION=2.3.2 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY src/ ./src/
COPY alembic.ini ./
COPY README.md ./
RUN poetry install --only main


FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid 1001 --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/alembic.ini /app/alembic.ini

USER app
EXPOSE 8000

# NOTE: no image-level HEALTHCHECK — this runtime image is shared by app,
# worker, scheduler and migrate, but only `app` serves HTTP on :8000. The
# app's HTTP healthcheck is defined on the `app` service in docker-compose.yaml
# instead, so the non-HTTP services don't inherit a check they can never pass.
# Web-worker count comes from WEB_CONCURRENCY (gunicorn honors it natively when
# --workers is omitted). Set per-environment in .env; docker-compose.yaml
# defaults the app service to 2.
CMD ["gunicorn", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--graceful-timeout", "30", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "learnic.web:create_app_production"]


FROM builder AS dev

RUN poetry install --with dev

CMD ["uvicorn", \
     "learnic.web:create_app_production", \
     "--factory", \
     "--reload", \
     "--reload-dir", "/app/src", \
     "--host", "0.0.0.0", \
     "--port", "8000"]

set dotenv-load := true

_default:
    @just --list --unsorted

[doc("Copy .env.dist to .env, install deps with dev group, install pre-commit hooks")]
bootstrap:
    cp -n .env.dist .env || true
    poetry install

[doc("Run app + worker locally: bring up dev stack, apply migrations, start both with reload")]
serve: dev-up
    #!/usr/bin/env bash
    poetry run alembic upgrade head
    poetry run uvicorn learnic.web:create_app_production --factory --reload &
    poetry run taskiq worker learnic.worker:broker --reload &
    wait

[doc("Run TaskIQ worker only (useful when debugging tasks without the API)")]
worker:
    poetry run taskiq worker learnic.worker:broker --reload

[doc("Run ruff check + ruff format + codespell")]
lint:
    poetry run ruff check --exit-non-zero-on-fix
    poetry run ruff format
    poetry run codespell

[doc("Run mypy + bandit + semgrep")]
static:
    poetry run mypy --config-file pyproject.toml
    poetry run bandit -c pyproject.toml -r src
    poetry run semgrep scan --config auto --error

[doc("Start dev Postgres, MinIO and Redis in background and wait until healthy")]
dev-up:
    docker compose -f docker-compose.dev.yaml up -d --wait postgres minio redis
    docker compose -f docker-compose.dev.yaml run --rm minio-bootstrap

[doc("Stop and remove dev containers")]
dev-down:
    docker compose -f docker-compose.dev.yaml down

[doc("Build and start the full production-like stack (Postgres + migrate + app + Caddy)")]
prod-up:
    docker compose up -d --build --wait

[doc("Stop production-like stack and remove orphan containers")]
prod-down:
    docker compose down --remove-orphans

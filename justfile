set dotenv-load := true

compose_dev := "docker compose -f docker-compose.dev.yaml"

_default:
    @just --list --unsorted

[doc("Run ruff + codespell + mypy + bandit + semgrep")]
check:
    poetry run ruff check --exit-non-zero-on-fix
    poetry run ruff format
    poetry run codespell
    poetry run mypy --config-file pyproject.toml
    poetry run bandit -c pyproject.toml -r src
    poetry run semgrep scan --config auto --error

[doc("Start dev infra, sync .env, run app + worker with reload")]
dev-up:
    #!/usr/bin/env bash
    set -euo pipefail
    {{compose_dev}} up -d --wait postgres minio redis
    {{compose_dev}} exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -v ON_ERROR_STOP=1 -q -v new_pw="$POSTGRES_PASSWORD" >/dev/null <<SQL
    ALTER USER "$POSTGRES_USER" WITH PASSWORD :'new_pw';
    SQL
    {{compose_dev}} run --rm minio-bootstrap
    poetry run alembic upgrade head
    poetry run uvicorn learnic.web:create_app_production --factory --reload &
    poetry run taskiq worker learnic.worker:broker --reload &
    wait

[doc("Stop dev infra (keeps volumes)")]
dev-down:
    {{compose_dev}} down

[doc("Build and start the production-like stack")]
prod-up:
    docker compose up -d --build --wait

[doc("Stop the production-like stack (keeps volumes)")]
prod-down:
    docker compose down

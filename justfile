set dotenv-load := true

compose_dev := "docker compose -f docker-compose.dev.yaml"

_default:
    @just --list --unsorted

[private]
[doc("Kill any processes listening on the given TCP port")]
_kill-port port:
    #!/usr/bin/env bash
    set -euo pipefail
    pids=$(lsof -ti tcp:{{ port }} 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "Freeing port {{ port }} (killing PIDs: $pids)"
        kill -9 $pids 2>/dev/null || true
    fi

[doc("Run ruff + codespell + mypy + bandit + semgrep")]
check:
    poetry run ruff check --exit-non-zero-on-fix
    poetry run ruff format
    poetry run codespell
    poetry run mypy --config-file pyproject.toml
    poetry run bandit -c pyproject.toml -r src
    poetry run semgrep scan --config auto --error

[doc("Start dev infra, sync .env, run app + worker + scheduler with reload")]
dev-up:
    #!/usr/bin/env bash
    set -euo pipefail
    just _kill-port "$UVICORN_PORT"
    {{compose_dev}} up -d --wait postgres minio redis
    {{compose_dev}} exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -v ON_ERROR_STOP=1 -q -v new_pw="$POSTGRES_PASSWORD" >/dev/null <<SQL
    ALTER USER "$POSTGRES_USER" WITH PASSWORD :'new_pw';
    SQL
    {{compose_dev}} run --rm minio-bootstrap
    poetry run alembic upgrade head
    poetry run uvicorn learnic.web:create_app_production --factory --reload &
    poetry run taskiq worker learnic.worker:broker --reload &
    poetry run taskiq scheduler learnic.worker:scheduler &
    wait

[doc("Stop dev infra (keeps volumes)")]
dev-down:
    {{compose_dev}} down

[private]
[doc("Create the shared external edge network if it doesn't exist yet")]
_net:
    docker network inspect learnic-edge >/dev/null 2>&1 || docker network create learnic-edge

# Compose file list: base + (unless REDIS/POSTGRES=external) the bundled overlays.
# docker-compose.redis.yaml / docker-compose.postgres.yaml add an in-stack Redis /
# PostgreSQL and are the DEFAULT; set REDIS=external / POSTGRES=external (env or
# .env) to use a managed/host service instead (point its URL / POSTGRES_HOST in .env).
_compose_files := "-f docker-compose.yaml"

[doc("Build and start the production stack with the API edge (split / two-host deploy)")]
prod-up:
    #!/usr/bin/env bash
    set -euo pipefail
    just _net
    just _kill-port 80
    just _kill-port 443
    files="{{ _compose_files }}"
    if [ "${REDIS:-bundled}" != "external" ]; then
        files="$files -f docker-compose.redis.yaml"
    fi
    if [ "${POSTGRES:-bundled}" != "external" ]; then
        files="$files -f docker-compose.postgres.yaml"
    fi
    docker compose $files up -d --build --wait
    # Caddyfile is a bind mount, so `up -d` won't recreate caddy when only the file
    # content changed, and Caddy doesn't watch it. Gracefully reload to apply config
    # edits with zero downtime (harmless re-apply on a fresh start; a broken config
    # makes reload exit non-zero under `set -e` while the old config keeps serving).
    docker compose $files exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile

[doc("Start as the SINGLE co-located edge — Caddy fronts BOTH frontend + API. Run the frontend with `just prod-up-colocated`.")]
prod-up-colocated:
    #!/usr/bin/env bash
    set -euo pipefail
    just _net
    just _kill-port 80
    just _kill-port 443
    files="{{ _compose_files }}"
    if [ "${REDIS:-bundled}" != "external" ]; then
        files="$files -f docker-compose.redis.yaml"
    fi
    if [ "${POSTGRES:-bundled}" != "external" ]; then
        files="$files -f docker-compose.postgres.yaml"
    fi
    BACKEND_CADDYFILE=./deploy/caddy/Caddyfile.colocated docker compose $files up -d --build --wait
    # Caddyfile is a bind mount, so `up -d` won't recreate caddy when only the file
    # content changed, and Caddy doesn't watch it. Gracefully reload to apply config
    # edits with zero downtime (harmless re-apply on a fresh start; a broken config
    # makes reload exit non-zero under `set -e` while the old config keeps serving).
    docker compose $files exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile

[doc("Stop the production-like stack (keeps volumes)")]
prod-down:
    #!/usr/bin/env bash
    set -euo pipefail
    files="{{ _compose_files }}"
    if [ "${REDIS:-bundled}" != "external" ]; then
        files="$files -f docker-compose.redis.yaml"
    fi
    if [ "${POSTGRES:-bundled}" != "external" ]; then
        files="$files -f docker-compose.postgres.yaml"
    fi
    docker compose $files down

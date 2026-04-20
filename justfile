set dotenv-load := true

_default:
    @just --list --unsorted

[doc("Copy .env.dist to .env, install deps with dev group, install pre-commit hooks")]
bootstrap:
    cp -n .env.dist .env || true
    poetry install

[doc("Sync virtualenv to poetry.lock (removes anything not in lock)")]
sync:
    poetry sync --with dev

[doc("Run app locally: apply migrations then start uvicorn with reload")]
serve:
    poetry run alembic upgrade head
    poetry run uvicorn learnic.web:create_app_production --factory --reload

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

[doc("Run pre-commit on all files")]
pre-commit:
    poetry run pre-commit run --show-diff-on-failure --color=always --all-files

[doc("Start dev Postgres in background and wait until healthy")]
dev-up:
    docker compose -f docker-compose.dev.yaml up -d --wait

[doc("Stop and remove dev containers")]
dev-down:
    docker compose -f docker-compose.dev.yaml down

[doc("Run tests with coverage (spins up dev DB for the duration)")]
test *args: dev-up
    poetry run coverage run -m pytest -x --ff {{ args }}
    just dev-down

[doc("Run tests then print combined coverage report")]
test-cov *args:
    just test {{ args }}
    poetry run coverage combine
    poetry run coverage report --show-missing --skip-covered --sort=cover --precision=2
    rm -f .coverage*

[doc("Build and start the full production-like stack (Postgres + migrate + app + Caddy)")]
prod-up:
    docker compose up -d --build --wait

[doc("Stop production-like stack and remove orphan containers")]
prod-down:
    docker compose down --remove-orphans

[doc("Follow logs from production-like stack (optionally pass a service name)")]
prod-logs *args:
    docker compose logs -f {{ args }}

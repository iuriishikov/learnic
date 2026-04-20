set dotenv-load := true

bootstrap:
    cp -n .env.dist .env || true
    poetry install

venv-sync:
    poetry install

serve:
    poetry run python -m learnic

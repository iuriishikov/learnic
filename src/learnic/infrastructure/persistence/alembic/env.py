from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from learnic.infrastructure.configs import load_configs
from learnic.infrastructure.persistence.models import (
    email_token as _email_token_model,
    file as _file_model,
    refresh_token as _refresh_token_model,
    signup_session as _signup_session_model,
    token_denylist as _token_denylist_model,
    user as _user_model,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry

_ = (
    _user_model,
    _refresh_token_model,
    _email_token_model,
    _signup_session_model,
    _token_denylist_model,
    _file_model,
)  # ensure tables register on mapper_registry.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", load_configs().postgres.dsn_sync)

target_metadata = mapper_registry.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

import importlib
import pkgutil
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from learnic.infrastructure.configs import load_configs
from learnic.infrastructure.persistence import models as _models_pkg
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _import_all_model_modules() -> None:
    """Import every ``models/*`` submodule so its ``sa.Table`` registers.

    Each model module defines its tables at import time via
    ``sa.Table(..., mapper_registry.metadata, ...)``, so importing the
    whole package makes ``target_metadata`` reflect the FULL schema.
    Without this, ``target_metadata`` held only a handful of hand-listed
    tables and ``alembic revision --autogenerate`` would emit
    ``op.drop_table(...)`` for every table it could not see. Walking the
    package keeps the set complete with zero maintenance as aggregates
    are added (no hand-listed import to forget).
    """
    for module_info in pkgutil.iter_modules(_models_pkg.__path__):
        if module_info.name == "registry":
            continue
        importlib.import_module(f"{_models_pkg.__name__}.{module_info.name}")


_import_all_model_modules()

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

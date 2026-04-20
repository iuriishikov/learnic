"""TaskIQ worker entry point.

Run with:
    poetry run taskiq worker learnic.worker:broker

The broker is imported from :mod:`learnic.infrastructure.tasks.broker`
and re-exported here so the CLI target line stays symmetrical with
``learnic.web:create_app_production``.

Importing :mod:`learnic.infrastructure.tasks.handlers` ensures every
``@broker.task`` decorator has run before the worker starts consuming.
"""

from dishka.integrations.taskiq import setup_dishka

from learnic.bootstrap import setup_configs, setup_map_tables
from learnic.infrastructure.tasks import handlers as _handlers  # noqa: F401
from learnic.infrastructure.tasks.broker import broker
from learnic.ioc import setup_providers

setup_map_tables()
_container = setup_providers(setup_configs())
setup_dishka(container=_container, broker=broker)

__all__ = ["broker"]

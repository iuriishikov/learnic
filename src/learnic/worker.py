"""TaskIQ worker + scheduler entry points.

Two CLI targets share this module:

* Worker — consumes tasks from the broker queue::

      poetry run taskiq worker learnic.worker:broker

* Scheduler — reads ``schedule=[{"cron": ...}]`` labels off every
  ``@broker.task`` (via :class:`LabelScheduleSource`) and enqueues
  the matching task at the configured cadence::

      poetry run taskiq scheduler learnic.worker:scheduler

The two are separate OS processes in production. The worker can
scale horizontally; the scheduler MUST be a single replica or the
same job lands in the queue N times per tick. In Kubernetes that
means ``replicas: 1`` on the scheduler Deployment.

Importing :mod:`learnic.infrastructure.tasks.handlers` ensures every
``@broker.task`` decorator (and its ``schedule=...`` label) has been
registered before either process inspects the broker.
"""

from dishka.integrations.taskiq import setup_dishka
from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from learnic.bootstrap import setup_configs, setup_map_tables
from learnic.infrastructure.tasks import handlers as _handlers  # noqa: F401
from learnic.infrastructure.tasks.broker import broker
from learnic.ioc import setup_providers

setup_map_tables()
_container = setup_providers(setup_configs())
setup_dishka(container=_container, broker=broker)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
"""Cron-driven enqueuer. Reads ``schedule=`` labels from
``@broker.task`` decorators. See module docstring for the CLI
command and the single-replica caveat."""

__all__ = ["broker", "scheduler"]

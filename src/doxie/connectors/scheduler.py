"""APScheduler-based scheduler for periodic connector syncing.

Provides helpers to schedule and manage periodic sync jobs for connectors.
This is a minimal skeleton; full error handling and persistence will be added later.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from doxie.connectors.base_connector import BaseConnector


class ConnectorScheduler:
    """Schedules periodic runs of a connector's sync method using AsyncIOScheduler."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._started = False

    def start(self) -> None:
        """Start the underlying scheduler if not already started."""
        if not self._started:
            self._scheduler.start(paused=False)
            self._started = True

    def shutdown(self, *, wait: bool = True) -> None:
        """Shut down the scheduler."""
        if self._started:
            self._scheduler.shutdown(wait=wait)
            self._started = False

    def schedule_sync(
        self,
        connector: BaseConnector,
        *,
        interval: timedelta = timedelta(minutes=15),
        job_id: Optional[str] = None,
        replace_existing: bool = True,
    ) -> None:
        """Schedule periodic execution of `connector.sync()`.

        Parameters
        ----------
        connector: BaseConnector
            The connector instance to run.
        interval: timedelta
            How often to run the sync job (default 15 minutes).
        job_id: Optional[str]
            Explicit job id to allow replacing/canceling.
        replace_existing: bool
            If True, replace any existing job with the same id.
        """

        async def _job() -> None:
            await connector.sync()

        trigger = IntervalTrigger(seconds=int(interval.total_seconds()))
        self._scheduler.add_job(
            _job,
            trigger=trigger,
            id=job_id,
            replace_existing=replace_existing,
            max_instances=1,
            coalesce=True,
        )

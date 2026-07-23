import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from denmark_academy.current_affairs.service import CurrentAffairsService

logger = logging.getLogger(__name__)


class CurrentAffairsScheduler:
    """Single-instance, coalesced refresh and expiry jobs."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self.service = CurrentAffairsService()
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self.scheduler.add_job(
            self._fetch_and_process,
            trigger=IntervalTrigger(hours=6),
            id="fetch_current_affairs",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )
        self.scheduler.add_job(
            self._cleanup_expired,
            trigger=IntervalTrigger(hours=24),
            id="cleanup_current_affairs",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        self.scheduler.start()
        self._running = True
        asyncio.create_task(self._startup_maintenance())
        logger.info("Current Affairs scheduler started")

    def stop(self) -> None:
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False

    async def _startup_maintenance(self) -> None:
        await self._cleanup_expired()
        await self._fetch_and_process()

    async def _fetch_and_process(self) -> None:
        try:
            stats = await self.service.ensure_priority_pool(force=True)
            logger.info("Scheduled Current Affairs refresh: %s", stats)
        except Exception:
            logger.exception("Scheduled Current Affairs refresh failed")

    async def _cleanup_expired(self) -> None:
        try:
            result = await asyncio.to_thread(self.service.cleanup_expired)
            logger.info("Scheduled Current Affairs cleanup: %s", result)
        except Exception:
            logger.exception("Scheduled Current Affairs cleanup failed")


_scheduler: CurrentAffairsScheduler | None = None


def get_scheduler() -> CurrentAffairsScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = CurrentAffairsScheduler()
    return _scheduler

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from typing import Callable
import logging

logger = logging.getLogger(__name__)
class SchedulerManager:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    def start(self):
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("✅ SchedulerManager: Started.")

    def shutdown(self):
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("🛑 SchedulerManager: Shut down.")

    def add_job(self, func: Callable, job_id: str, trigger: BaseTrigger, replace: bool = True, **job_kwargs):
        try:
            if self._scheduler.get_job(job_id):
                if replace:
                    self._scheduler.remove_job(job_id)
                else:
                    logger.warning(f"⚠️ Job {job_id} already exists. Skipping.")
                    return

            self._scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
                kwargs=job_kwargs
            )
            logger.info(f"➕ Job '{job_id}' scheduled with args: {job_kwargs}")
        except Exception as e:
            logger.error(f"❌ Failed to add job {job_id}: {e}")

    def remove_job(self, job_id: str) -> bool:
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            logger.info(f"➖ Job '{job_id}' removed.")
            return True
        return False
        
    def get_job(self, job_id: str):
        return self._scheduler.get_job(job_id)
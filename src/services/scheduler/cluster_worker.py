import asyncio
import os
import logging
from apscheduler.triggers.cron import CronTrigger
from src.services.scheduler.scheduler import SchedulerManager
from src.services.scheduler.job import cleanup_task, scheduled_database_task
from src.extensions import settings, redis_client
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

class ClusterWorker:
    def __init__(self, scheduler_manager: SchedulerManager):
        self.scheduler = scheduler_manager
        self.lock_key = "worker_leader_lock"
        self.identity = str(os.getpid())
        self.is_leader = False
        self._maintain_task = None

    async def start(self):
        print("🚀 ClusterWorker: Starting up...")
        if not settings.get("enable_worker", False):
            return
        try:
            acquired = await redis_client.set(
                self.lock_key, 
                self.identity, 
                nx=True, 
                ex=30
            )

            if acquired:
                await self._become_leader()
            else:
                current = await redis_client.get(self.lock_key)
                logger.info(f"💤 Node {self.identity} is follower. Leader is {current}")

        except Exception as e:
            logger.error(f"❌ Error during worker startup: {e}")

    async def stop(self):
        """
        Called on application shutdown.
        """
        # Stop the maintenance loop
        if self._maintain_task:
            self._maintain_task.cancel()
            try:
                await self._maintain_task
            except asyncio.CancelledError:
                pass

        # If leader, stop scheduler and release lock
        if self.is_leader:
            self.scheduler.shutdown()
            await self._release_lock()

    async def _become_leader(self):
        """
        Logic to execute when this node becomes the leader.
        """
        self.is_leader = True
        logger.info(f"👑 Node {self.identity} acquired leadership")

        # 1. Register Jobs (Define your Cron/Intervals here)
        self._register_default_jobs()

        # 2. Start Scheduler
        self.scheduler.start()

        # 3. Start Lock Maintenance Loop
        self._maintain_task = asyncio.create_task(self._maintain_leadership())

    def _register_default_jobs(self):
        # self.scheduler.add_job(
        #     func=scheduled_database_task,
        #     job_id="daily_db_sync",
        #     trigger=CronTrigger(hour=4, minute=30)
        # )

        # self.scheduler.add_job(
        #     func=cleanup_task,
        #     job_id="cleanup_service",
        #     trigger=IntervalTrigger(seconds=5)
        # )
        ...

    async def _maintain_leadership(self):
        while self.is_leader:
            try:
                await asyncio.sleep(20)
                await redis_client.expire(self.lock_key, 30)
            except Exception as e:
                logger.error(f"⚠️ Error maintaining leadership: {e}")
                
    async def _release_lock(self):
        try:
            current = await redis_client.get(self.lock_key)
            if current == self.identity:
                await redis_client.delete(self.lock_key)
                logger.info("👋 Leadership released.")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
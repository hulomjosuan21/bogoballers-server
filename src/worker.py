from apscheduler.triggers.cron import CronTrigger
from src.extensions import AsyncSession, settings
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
class Worker:
    def __init__(self, task):
        executors = {
            "default": AsyncIOExecutor()
        }
        self.scheduler = AsyncIOScheduler(timezone="UTC", executors=executors)
        self.task = task
        self._register_tasks()

    def _register_tasks(self):
        tasks_with_session = {
            # self.task.task_with_session: CronTrigger(hour=16,minute=31)
        }

        tasks_without_session = {
            # self.task.task_without_session: IntervalTrigger(seconds=settings["interval"])
            self.task.task_without_session: IntervalTrigger(seconds=settings["interval"])
        }

        for task_method, trigger in tasks_with_session.items():
            async def wrapper(task_method=task_method):
                async with AsyncSession() as session:
                    async with session.begin():
                        try:
                            await task_method(session)
                        except Exception as e:
                            print(f"Error in {task_method.__name__}: {e}")
            self.scheduler.add_job(wrapper, trigger)

        for task_method, trigger in tasks_without_session.items():
            async def wrapper(task_method=task_method):
                try:
                    await task_method()
                except Exception as e:
                    print(f"Error in {task_method.__name__}: {e}")
            self.scheduler.add_job(wrapper, trigger)

    def start(self):
        self.scheduler.start()
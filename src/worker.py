import os
from apscheduler.triggers.cron import CronTrigger
from src.extensions import AsyncSession, redis_client
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor

async def session_wrapper_job(worker_instance, task_method, *args):
    if not await worker_instance._is_leader():
        print(f"Worker leadership lost, skipping task: {task_method.__name__}")
        return
        
    async with AsyncSession() as session:
        async with session.begin():
            try:
                await task_method(session, *args)
            except Exception as e:
                print(f"Error in {task_method.__name__}: {e}")

async def no_session_wrapper_job(worker_instance, task_method, *args):
    if not await worker_instance._is_leader():
        print(f"Worker leadership lost, skipping task: {task_method.__name__}")
        return
        
    try:
        await task_method(*args)
    except Exception as e:
        print(f"Error in {task_method.__name__}: {e}")

class Worker:
    def __init__(self, task):
        executors = {
            "default": AsyncIOExecutor()
        }
        
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 30
        }
        
        self.scheduler = AsyncIOScheduler(
            timezone="UTC", 
            executors=executors,
            job_defaults=job_defaults
        )
        self.task = task
        self.is_running = False
        self._register_tasks()

    def _register_tasks(self):
        tasks_with_session = {
            self.task.daily_match_reminder_job: CronTrigger(hour='10', minute='18,19,20,21,22')
        }

        tasks_without_session = {
            # self.task.task_without_session: IntervalTrigger(seconds=5),
            # self.task.task_without_session: CronTrigger(hour='13,13',minute='31,32')
        }

        if tasks_with_session:
            for task_method, trigger in tasks_with_session.items():
                self.scheduler.add_job(
                    session_wrapper_job,
                    trigger, 
                    args=[self, task_method, 1],
                    id=f"{task_method.__name__}_with_session",
                    replace_existing=True
                )
        else:
            print("No tasks with session to register")
         
        if tasks_without_session:
            for task_method, trigger in tasks_without_session.items():
                self.scheduler.add_job(
                    no_session_wrapper_job,
                    trigger,
                    args=[self, task_method],
                    id=f"{task_method.__name__}_no_session",
                    replace_existing=True
                )
        else:
            print("No tasks without session to register")
            
    async def _is_leader(self):
        try:
            current_leader = await redis_client.get("worker_leader_lock")
            return current_leader == str(os.getpid())
        except Exception as e:
            return False

    def start(self):
        if not self.is_running:
            try:
                self.scheduler.start()
                self.is_running = True
                print(f"Worker/Scheduler started successfully in process {os.getpid()}!")
                
                jobs = self.scheduler.get_jobs()
                if jobs:
                    print(f"Registered {len(jobs)} scheduled jobs:")
                    for job in jobs:
                        print(f"  - {job.id}: {job.trigger}")
                else:
                    print("No jobs registered")
                    
            except Exception as e:
                print(f"Error starting worker: {e}")
                self.is_running = False

    def stop(self):
        if self.is_running:
            try:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                print("Worker/Scheduler stopped successfully!")
            except Exception as e:
                print(f"Error stopping worker: {e}")

    def get_job_status(self):
        if not self.is_running:
            return {"status": "stopped", "jobs": []}
            
        jobs = self.scheduler.get_jobs()
        job_info = []
        
        for job in jobs:
            job_info.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
            
        return {
            "status": "running",
            "process_id": os.getpid(),
            "job_count": len(jobs),
            "jobs": job_info
        }
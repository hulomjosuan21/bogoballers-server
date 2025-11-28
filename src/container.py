from src.services.scheduler.cluster_worker import ClusterWorker
from src.services.scheduler.scheduler import SchedulerManager

scheduler_manager = SchedulerManager()
cluster_worker = ClusterWorker(scheduler_manager)
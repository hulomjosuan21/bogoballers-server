import traceback
from quart import Blueprint
from src.services.scheduler.job_wrapper import monitor_match_status_wrapper
from src.utils.api_response import ApiException, ApiResponse

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/scheduler')

@scheduler_bp.post('/add-test-job')
async def add_test_job():
    from src.container import scheduler_manager
    from apscheduler.triggers.interval import IntervalTrigger
    import datetime

    def test_job():
        print(f"Test job executed at {datetime.datetime.now()}")

    trigger = IntervalTrigger(seconds=5)
    scheduler_manager.add_job(test_job, job_id="test_job", trigger=trigger)

    return {"status": "job_added"}, 200

@scheduler_bp.post('/monitor-match/<league_match_id>')
async def add_match_monitor_job(league_match_id: str):
    try:
        if not league_match_id:
            raise ApiException("league_match_id is required")

        result = await monitor_match_status_wrapper(league_match_id)
        
        return await ApiResponse.success(message=result)

    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
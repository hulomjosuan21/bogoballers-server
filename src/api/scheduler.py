import traceback
from quart import Blueprint, request, jsonify
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.services.scheduler.job import monitor_match_status
from src.models.match import LeagueMatchModel
from src.container import scheduler_manager
from src.extensions import db_session
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

        async with db_session() as session:
            match = await session.get(LeagueMatchModel, league_match_id)
            
            if not match:
                raise ApiException("Match not found")
                
            if not match.scheduled_date:
                trigger = IntervalTrigger(seconds=30)
                trigger_info = "Interval (30s) - No scheduled date found"
            else:
                from datetime import datetime, timezone
                
                h = match.scheduled_date.hour
                m = match.scheduled_date.minute
                
                # trigger = CronTrigger(hour=h, minute=m, timezone=timezone.utc)
                trigger = IntervalTrigger(seconds=15)
                trigger_info = f"Cron (Daily at {h:02d}:{m:02d} UTC)"
                
                now = datetime.now(timezone.utc)
                scheduled_today = now.replace(hour=h, minute=m, second=0, microsecond=0)
                
                if now >= scheduled_today:
                    await monitor_match_status(league_match_id)

            scheduler_manager.add_job(
                func=monitor_match_status,
                job_id=league_match_id, 
                trigger=trigger,
                league_match_id=league_match_id
            )

            return await ApiResponse.payload({
                "status": "scheduled", 
                "job_id": league_match_id, 
                "trigger": trigger_info,
                "match": f"{match.display_name} ({match.scheduled_date})"
            })
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
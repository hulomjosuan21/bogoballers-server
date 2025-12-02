from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.services.notification_service import create_notification, send_notification
from src.models.team import LeagueTeamModel
from src.services.scheduler.job import monitor_match_status
from src.extensions import notification_limit
from src.models.match import LeagueMatchModel
from src.container import scheduler_manager
from src.extensions import db_session
from src.utils.api_response import ApiException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.utils.notification_utils import get_valid_fcm_for_match

async def monitor_match_status_wrapper(league_match_id: str):
    print("⏳ Setting up monitor for match:", league_match_id)
    async with db_session() as session:
        stmt = (
            select(LeagueMatchModel)
            .options(
                selectinload(LeagueMatchModel.home_team).selectinload(LeagueTeamModel.team),
                selectinload(LeagueMatchModel.away_team).selectinload(LeagueTeamModel.team),
            )
            .where(LeagueMatchModel.league_match_id == league_match_id)
        )
        result = await session.execute(stmt)
        match_data = result.scalar_one_or_none()        
        if not match_data:
            raise ApiException("Match not found")
    
        if not match_data.scheduled_date:
            raise ApiException("Match does not have a scheduled date")
    
        home_team_name = match_data.home_team.team.team_name
        away_team_name = match_data.away_team.team.team_name
        
        recipients = await get_valid_fcm_for_match(session, league_match_id, limit=notification_limit)
        
        if len(recipients.home) > 0 :
            for recipient in recipients.home:
                data_payload = {
                    "title": "Upcoming Game Reminder!",
                    "message": (
                        f"Your team, the {home_team_name}, has a game "
                        f"against the team {away_team_name} "
                        f"scheduled for {match_data.scheduled_date.strftime('%Y-%m-%d %I:%M %p')}."
                    ),
                    "to_id": recipient.user_id,
                    "fcm_token": recipient.fcm_token,
                }
                
                notif = await create_notification(data=data_payload)
                await send_notification(recipient.fcm_token, notif, enable=True)
        
        if len(recipients.away) > 0 :
            for recipient in recipients.away:
                data_payload = {
                    "title": "Upcoming Game Reminder!",
                    "message": (
                        f"Your team, the {away_team_name}, has a game "
                        f"against the team {home_team_name} "
                        f"scheduled for {match_data.scheduled_date.strftime('%Y-%m-%d %I:%M %p')}."
                    ),
                    "to_id": recipient.user_id,
                    "fcm_token": recipient.fcm_token,
                }
                notif = await create_notification(data=data_payload)
                await send_notification(recipient.fcm_token, notif, enable=True)
                

        from datetime import datetime, timezone
        
        h = match_data.scheduled_date.hour
        m = match_data.scheduled_date.minute
        
        trigger = CronTrigger(hour=h, minute=m, timezone=timezone.utc)
        
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

        return f"{match_data.display_name} ({match_data.scheduled_date})"
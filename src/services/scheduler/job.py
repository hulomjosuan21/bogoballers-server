

import asyncio

from sqlalchemy import select
import logging
from sqlalchemy.orm import selectinload
from src.models.team import LeagueTeamModel
from src.extensions import db_session
from src.services.notification_service import NotificationService, create_and_send_notification
from src.utils.notification_utils import get_valid_fcm_for_match

logger = logging.getLogger(__name__)

notification_service = NotificationService()

async def scheduled_database_task():
    print("⏳ CRON: Starting scheduled database task...")
    async with db_session() as session:
        try:
            print("✅ CRON: Database check successful.")
        except Exception as e:
            print(f"❌ CRON: Error: {e}")

async def cleanup_task():
    print("🧹 INTERVAL: Starting cleanup task...")
    async with db_session() as session:
        try:
            await asyncio.sleep(1)
            print("✅ INTERVAL: Cleanup finished.")
        except Exception as e:
            print(f"❌ INTERVAL: Error: {e}")
            
async def monitor_match_status(league_match_id: str):
    from src.container import scheduler_manager
    from src.models.match import LeagueMatchModel 

    async with db_session() as session:
        try:
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
                logger.warning(f"❌ Match {league_match_id} not found. Removing job.")
                scheduler_manager.remove_job(league_match_id)
                return

            home_team_name = match_data.home_team.team.team_name
            away_team_name = match_data.away_team.team.team_name
            
            if match_data.status != "Scheduled":
                print(f"✅ Match '{match_data.display_name}' is {match_data.status}. Auto-removing job.")
                scheduler_manager.remove_job(league_match_id)
            else:
                print(f"📢 Monitor: Match '{home_team_name} vs {away_team_name}' is currently {match_data.status}.")
                
                # recipients = await get_valid_fcm_for_match(session, league_match_id, limit=4)
                
                # tasks = []
                
                # for recipient in recipients.home:
                #     data_payload = {
                #         "title": "Upcoming Game Reminder!",
                #         "message": (
                #             f"Your team, the {home_team_name}, has a game "
                #             f"against the team {away_team_name} "
                #             f"scheduled for {match_data.scheduled_date.strftime('%Y-%m-%d %I:%M %p')}."
                #         ),
                #         "to_id": recipient.user_id,
                #         "fcm_token": recipient.fcm_token,
                #     }
                #     tasks.append(create_and_send_notification(data=data_payload))
                
                # for recipient in recipients.away:
                #     data_payload = {
                #         "title": "Upcoming Game Reminder!",
                #         "message": (
                #             f"Your team, the {away_team_name}, has a game "
                #             f"against the team {home_team_name} "
                #             f"scheduled for {match_data.scheduled_date.strftime('%Y-%m-%d %I:%M %p')}."
                #         ),
                #         "to_id": recipient.user_id,
                #         "fcm_token": recipient.fcm_token,
                #     }
                #     tasks.append(create_and_send_notification(data=data_payload))
                # await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"❌ Error monitoring match {league_match_id}: {e}")
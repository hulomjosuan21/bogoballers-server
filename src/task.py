from asyncio import to_thread
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Date, and_, distinct, select
from src.services.notification_service import NotificationService
from src.models.user import UserModel
from src.models.match import LeagueMatchModel
from src.models.player import LeaguePlayerModel, PlayerModel, PlayerTeamModel
from src.models.team import LeagueTeamModel
from firebase_admin import messaging
from sqlalchemy.orm import joinedload

notification_service = NotificationService()

class Task:
    async def daily_match_reminder_job(self, session, limit: Optional[int] = None):
        now = datetime.now(timezone.utc)
        
        matches_to_remind = await session.execute(
            select(LeagueMatchModel)
            .options(
                joinedload(LeagueMatchModel.home_team).joinedload(LeagueTeamModel.team),
                joinedload(LeagueMatchModel.away_team).joinedload(LeagueTeamModel.team),
            )
            .where(
                and_(
                    LeagueMatchModel.scheduled_date.is_not(None),
                    LeagueMatchModel.scheduled_date > now,
                    LeagueMatchModel.status != "Completed"
                )
            )
            .limit(limit)
        )
        
        
        matches_to_remind = matches_to_remind.scalars().all()
        if not matches_to_remind:
            print("No matches found that require a reminder.")
            return
        
        for match in matches_to_remind:
            home_team_players = await session.execute(
                select(UserModel)
                .distinct()
                .join(PlayerModel)
                .join(PlayerTeamModel)
                .join(LeaguePlayerModel)
                .join(LeagueTeamModel)
                .where(
                    and_(
                        LeagueTeamModel.league_team_id == match.home_team_id,
                        UserModel.fcm_token.is_not(None)
                    )
                )
                .limit(limit)
            )
            
            home_team_users = home_team_players.scalars().all()

            away_team_players = await session.execute(
                select(UserModel)
                .distinct()
                .join(PlayerModel)
                .join(PlayerTeamModel)
                .join(LeaguePlayerModel)
                .join(LeagueTeamModel)
                .where(
                    and_(
                        LeagueTeamModel.league_team_id == match.away_team_id,
                        UserModel.fcm_token.is_not(None)
                    )
                )
                .limit(limit)
            )
            
            away_team_users = away_team_players.scalars().all()

            for user in home_team_users:
                data_payload = {
                    "title": "Upcoming Game Reminder!",
                    "message": (
                        f"Your team, the {match.home_team.team.team_name}, has a game "
                        f"against the team {match.away_team.team.team_name} "
                        f"scheduled for {match.scheduled_date.strftime('%Y-%m-%d %I:%M %p')}."
                    ),
                    "to_id": user.user_id,
                }
                
                await notification_service.create_notification(data=data_payload)

            for user in away_team_users:
                data_payload = {
                    "title": "Upcoming Game Reminder!",
                    "message": (
                        f"Your team, the {match.away_team.team.team_name}, has a game "
                        f"against the team {match.home_team.team.team_name} "
                        f"scheduled for {match.scheduled_date.strftime('%Y-%m-%d %I:%M %p')}."
                    ),
                    "to_id": user.user_id,
                }
                await notification_service.create_notification(data=data_payload)
        
        print("Daily match reminder job completed.")
        

    async def task_without_session(self):
        print("Something is working background...")
        fcm_token="dEfjxKGOS76hLJ7YiDx6Sd:APA91bHC-HGqcvsEcp6-0JYcyGH2aiyNmXMHi4pdTMvq4BOye8ffn8OtPaV2lj36KKVuEugEzadfQSlpFU1JNMvB-G0IVU94VTls2YBMXX2EzuT5WMQ-ACc"
        
        message_kwargs = {
            "notification": messaging.Notification(
                title="Test",
                body="Test Message"
            ),
            "token": fcm_token
        }

        message = messaging.Message(**message_kwargs)
        
        response = await to_thread(messaging.send, message)
        print("Success send...")
        
    async def task_with_session(self, session):
        user = await session.get(UserModel, "user-cd92523e-7a3d-433d-8f71-aff44840ae21")
        user.email = "dakit-admin@email.com"
        await session.commit()
        print("Update success..")
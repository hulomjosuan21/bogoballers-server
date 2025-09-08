from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
from src.models.team import TeamModel
from src.models.notification import NotificationModel
from src.utils.api_response import ApiException
from src.models.player import PlayerModel, PlayerTeamModel
from src.extensions import AsyncSession


class PlayerTeamService:
    async def get_player_team(self, session, player_team_id) -> PlayerTeamModel:
        return await session.get(PlayerTeamModel, player_team_id)
    
    async def add_many(self, data: dict):
        async with AsyncSession() as session:
            try:
                new_player_teams = [
                    PlayerTeamModel(
                        team_id=data.get('team_id'),
                        player_id=player_id,
                        is_accepted="Accepted"
                    )
                    for player_id in data.get('player_ids')
                ]
                session.add_all(new_player_teams)

                await session.commit()

                return f"Total added players: {len(new_player_teams)}"
            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e

    async def add_player_to_team(self, user_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                team = await session.get(TeamModel, data.get('team_id'))
                
                player_result = await session.execute(
                    select(PlayerModel)
                    .options(joinedload(PlayerModel.user))
                    .where(PlayerModel.player_id == data.get('player_id'))
                )
                player = player_result.scalars().first()
                
                if not team:
                    raise ApiException("No team found.")
                if not player:
                    raise ApiException("No player found.")
                
                existing = await session.execute(
                    select(PlayerTeamModel)
                    .where(
                        and_(
                            PlayerTeamModel.team_id == data.get('team_id'),
                            PlayerTeamModel.player_id == data.get('player_id')
                        )
                    )
                )
                if existing.scalars().first():
                    raise ApiException(f"{player.full_name} is already in {team.team_name}.")
                
                status = data.get('status', 'Invited')
                
                new_player_team = PlayerTeamModel(
                    team_id=data.get('team_id'),
                    player_id=data.get('player_id'),
                    is_accepted=status
                )
                session.add(new_player_team)
                
                status_messages = {
                    "Pending": f"Hang tight! Your request to join {team.team_name} is being reviewed.",
                    "Accepted": f"Your request to join {team.team_name} has been accepted! Welcome to the team.",
                    "Rejected": f"Your request to join {team.team_name} has been rejected.",
                    "Invited": f"You have been invited to join {team.team_name}."
                }

                friendly_message = status_messages.get(status, f"Status: {status}")

                notif = NotificationModel(
                    action_type="team_invitation",
                    action_id=data.get('team_id'),
                    title="Team Invitation",
                    message=friendly_message, 
                    from_id=user_id,
                    to_id=player.user_id,
                    image_url=data.get("team_logo_url", None) 
                )

                token = player.user.fcm_token
                if token:
                    await notif.send(token=token)

                session.add(notif)
                await session.commit()
                return "Success"
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e

    async def update_one(self, player_team_id: str, data: dict):
        try:
            async with AsyncSession() as session:
                player_team = await self.get_player_team(session=session,player_team_id=player_team_id)

                if not player_team:
                    raise ApiException("No Player found")
                
                player_team.copy_with(**data)
                await session.commit()
                
                return "Player updated successfully"
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            raise e
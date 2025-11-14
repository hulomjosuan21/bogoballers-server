from sqlalchemy import select, and_, update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
from src.services.notification_service import NotificationService
from src.models.team import TeamModel
from src.utils.api_response import ApiException
from src.models.player import PlayerModel, PlayerTeamModel
from src.extensions import AsyncSession

notif_service = NotificationService()

class PlayerTeamService:
    async def add_player_to_team(self, user_id: str, data: dict):
        async with AsyncSession() as session:
            try:
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
                    team_id=team.team_id,
                    player_id=player.player_id,
                    is_accepted=status
                )
                session.add(new_player_team)

                await session.commit()

                if status == "Invited":
                    await self._send_team_invite_notification(
                        to_user_id=player.user.user_id,
                        player_team_id=new_player_team.player_team_id,
                        team_name=team.team_name,
                        status=status
                    )
                    return f"{player.full_name} invited to {team.team_name} successfully."

                return "Success"

            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e

    async def _send_team_invite_notification(self, to_user_id: str, player_team_id: str, team_name: str, status: str):
        friendly_message = f"You have been invited to join {team_name}."

        await notif_service.create_notification({
            "to_id": to_user_id,
            "message": friendly_message,
            "title": f"Team Invite: {team_name}",
            "action_type": "team_invitation",
            "action_payload": {
                "player_team_id": player_team_id,
            },
        })
    
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
            
    async def add_players_to_teams(self, team_data_list: list):
        async with AsyncSession() as session:
            try:
                new_player_teams = []

                for team_data in team_data_list:
                    team_id = team_data.get("team_id")
                    player_ids = team_data.get("player_ids")

                    if not team_id:
                        raise ValueError("team_id is required")
                    if not player_ids:
                        raise ValueError("player_ids must not be empty")

                    for player_id in player_ids:
                        new_player_teams.append(
                            PlayerTeamModel(
                                team_id=team_id,
                                player_id=player_id,
                                is_accepted="Accepted"
                            )
                        )

                session.add_all(new_player_teams)
                await session.commit()

                return f"Total added players: {len(new_player_teams)}"

            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise

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
        
    async def toggle_team_captain(self, player_team_id: str):
        async with AsyncSession() as session:
            try:
                player_team = await self.get_player_team(session=session, player_team_id=player_team_id)
                if not player_team:
                    raise ApiException("No player found in this team.")

                if player_team.is_team_captain:
                    player_team.is_team_captain = False
                    await session.commit()
                    return f"{player_team.player.full_name} is no longer the team captain of {player_team.team.team_name}."

                await session.execute(
                    update(PlayerTeamModel)
                    .where(
                        and_(
                            PlayerTeamModel.team_id == player_team.team_id,
                            PlayerTeamModel.is_team_captain == True
                        )
                    )
                    .values(is_team_captain=False)
                )

                player_team.is_team_captain = True
                await session.commit()

                return f"{player_team.player.full_name} is now the team captain of {player_team.team.team_name}."

            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e

    async def delete_one(self, player_team_id: str):
        async with AsyncSession() as session:
            try:
                player_team = await self.get_player_team(session=session, player_team_id=player_team_id)
                if not player_team:
                    raise ApiException("No player found in this team.")

                if player_team.is_team_captain:
                    player_team.is_team_captain = False
                    await session.commit()
                    return f"{player_team.player.full_name} is no longer the team captain of {player_team.team.team_name}."

                await session.execute(
                    update(PlayerTeamModel)
                    .where(
                        and_(
                            PlayerTeamModel.team_id == player_team.team_id,
                            PlayerTeamModel.is_team_captain == True
                        )
                    )
                    .values(is_team_captain=False)
                )

                player_team.is_team_captain = True
                await session.commit()

                return f"{player_team.player.full_name} is now the team captain of {player_team.team.team_name}."

            except (IntegrityError, SQLAlchemyError) as e:
                await session.rollback()
                raise e
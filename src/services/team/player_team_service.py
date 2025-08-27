from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
from src.models.team import TeamModel
from src.models.notification import NotificationModel
from src.utils.api_response import ApiException
from src.models.player import PlayerModel, PlayerTeamModel
from src.extensions import AsyncSession


class PlayerTeamService:
    async def invite_player(self, user_id: str, data: dict):
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
                
                new_player_team = PlayerTeamModel(
                    team_id=data.get('team_id'),
                    player_id=data.get('player_id'),
                    is_accepted="Invited"
                )
                
                session.add(new_player_team)
                
                notif = NotificationModel(
                    action_type="team_invitation",
                    action_id=data.get('team_id'),
                    title="Team invitation",
                    message=f"You have been invited to join team {team.team_name}",
                    from_id=user_id,
                    to_id=player.user_id,
                    image_url="https://res.cloudinary.com/dod3lmxm6/image/upload/v1754626478/league_banners/ccu6bovxxiqfhtjp8io9.jpg"
                )
                
                token = player.user.fcm_token
                
                await notif.send(token=token)
                session.add(notif)
                await session.commit()
                
                return f"Invited Successfully. on {team.team_name}"
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise

    async def update_status(self, player_team_id: str = None, team_id: str = None, 
                           player_id: str = None, new_status: str = None):
        if not new_status:
            raise ApiException("new_status is required")

        if not player_team_id and not (team_id and player_id):
            raise ApiException("You must provide either player_team_id OR both team_id and player_id")
                
        async with AsyncSession() as session:
            try:
                if player_team_id:
                    player_team = await session.get(PlayerTeamModel, player_team_id)
                elif team_id and player_id:
                    stmt = select(PlayerTeamModel).where(
                        PlayerTeamModel.team_id == team_id,
                        PlayerTeamModel.player_id == player_id
                    )
                    result = await session.execute(stmt)
                    player_team = result.scalar_one_or_none()
                else:
                    raise ApiException("Either player_team_id or both team_id and player_id are required")

                if not player_team:
                    raise ApiException("Player-Team relation not found")

                player_team.is_accepted = new_status
                session.add(player_team)
                await session.commit()

                return "Status updated."
            except (IntegrityError, SQLAlchemyError):
                await session.rollback()
                raise
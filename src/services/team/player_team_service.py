from sqlalchemy import select
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
                if token:
                    await notif.send(token=token)
                session.add(notif)
                await session.commit()
                
                return f"Invited Successfully. on {team.team_name}"
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
        except (IntegrityError, SQLAlchemyError):
            await session.rollback()
            raise
import json
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from quart import Blueprint, request

from src.models.team import TeamModel
from src.models.notification import NotificationModel
from src.utils.api_response import ApiException, ApiResponse
from src.models.player import PlayerModel, PlayerTeamModel
from src.extensions import AsyncSession
from sqlalchemy.orm import joinedload
import traceback

player_team_bp = Blueprint('team-player',__name__,url_prefix='/player-team')

class PlayerTeamHandler:
    @staticmethod
    @player_team_bp.post('/invite')
    async def invite_player():
        try:
            user_id = request.args.get("user_id")
            data = await request.get_json()
            team_id = data.get('team_id')
            player_id = data.get('player_id')
            required_fields = [
                "team_id", "player_id",
            ]
            for field in required_fields:
                if not data.get(field):
                    raise ApiException(f"{field} is required")
                
            async with AsyncSession() as session:
                team = await session.get(TeamModel, team_id)
                player_result = await session.execute(
                        select(PlayerModel)
                        .options(joinedload(PlayerModel.user))
                        .where(PlayerModel.player_id == player_id)
                    )
                player = player_result.scalars().first()
                if not team:
                    raise ApiException("No team found.")
                if not player:
                    raise ApiException("No player found.")
                
                new_player_team = PlayerTeamModel(
                    team_id=team_id,
                    player_id=player_id,
                    is_accepted="Invited"
                )
                
                session.add(new_player_team)
                
                notif = NotificationModel(
                    action_type="team_invitation",
                    action_id=team_id,
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
                
                return await ApiResponse.success(message=f"Invited Successfully. on {team.team_name}")
        except (IntegrityError, SQLAlchemyError) as e:
            await session.rollback()
            return await ApiResponse.error(f"Error: {str(e)}")
        except Exception as e:
            return await ApiResponse.error(e)
        
    @staticmethod
    @player_team_bp.put('/update-status')
    async def update_status():
        try:
            data = await request.get_json()
            
            user_id = request.args.get('user_id')
            team_id = request.args.get("team_id")
            player_team_id = request.args.get("player_team_id")

            player_id = data.get('player_id')
            new_status = data.get("new_status")

            if not new_status:
                raise ApiException("new_status is required")

            if not player_team_id and not (team_id and player_id):
                        raise ApiException("You must provide either player_team_id OR both team_id and player_id")
                    
            async with AsyncSession() as session:
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

                return await ApiResponse.success(
                    message="Status updated.",
                )

        except Exception as e:
            return await ApiResponse.error(e)
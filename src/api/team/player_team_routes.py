from quart import Blueprint, request
from src.utils.api_response import ApiResponse
from src.services.team.player_team_service import PlayerTeamService
from src.utils.server_utils import validate_required_fields

player_team_bp = Blueprint('team-player', __name__, url_prefix='/player-team')

service = PlayerTeamService()

@player_team_bp.post('/invite')
async def invite_player_route():
    try:
        user_id = request.args.get("user_id")
        data = await request.get_json()
        required_fields = [ "team_id", "player_id" ]
        validate_required_fields(data, required_fields)
        result = await service.invite_player(user_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@player_team_bp.put('/update-status')
async def update_status_route():
    try:
        data = await request.get_json()
        
        user_id = request.args.get('user_id')
        team_id = request.args.get("team_id")
        player_team_id = request.args.get("player_team_id")

        player_id = data.get('player_id')
        new_status = data.get("new_status")
        
        result = await service.update_status(player_team_id, team_id, player_id, new_status)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
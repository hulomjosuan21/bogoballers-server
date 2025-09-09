import traceback
from quart import Blueprint, request
from src.utils.api_response import ApiResponse
from src.services.team.player_team_service import PlayerTeamService
from src.utils.server_utils import validate_required_fields

player_team_bp = Blueprint('team-player', __name__, url_prefix='/player-team')

service = PlayerTeamService()

@player_team_bp.post('/add-player')
async def add_player_route():
    try:
        user_id = request.args.get("user_id")
        data = await request.get_json()
        required_fields = [ "team_id", "player_id" ]
        validate_required_fields(data, required_fields)
        result = await service.add_player_to_team(user_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@player_team_bp.put('/update/<player_team_id>')
async def update_one_route(player_team_id: str):
    try:
        data = await request.get_json()
    
        result = await service.update_one(player_team_id=player_team_id, data=data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
    
@player_team_bp.post('/add/many')
async def add_many_route():
    try:
        data = await request.get_json()
    
        result = await service.add_many(data=data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@player_team_bp.post('/add/many-to-team')
async def add_many_to_teams_route():
    try:
        data = await request.get_json()
        result = await service.add_players_to_teams(data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
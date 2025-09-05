import traceback
from quart import Blueprint

from src.services.league.league_player_service import LeaguePlayerService
from src.utils.api_response import ApiResponse

league_player = Blueprint('league-player',__name__,url_prefix='/league-player')

service = LeaguePlayerService()

@league_player.get('/all/<league_id>/<league_category_id>')
async def get_all_route(league_id: str, league_category_id: str):
    try:
        result = await service.get_all(league_id=league_id, league_category_id=league_category_id)
        return await ApiResponse.payload([player.to_json() for player in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_player.post('/add-one/no-team/<league_id>/<league_category_id>/<player_id>')
async def add_one_no_team(league_id: str, league_category_id: str, player_id: str):
    try:
        result = await service.create_one_no_team(league_id=league_id,league_category_id=league_category_id,player_id=player_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
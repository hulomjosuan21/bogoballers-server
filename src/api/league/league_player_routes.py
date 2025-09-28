import traceback
from quart import Blueprint, request

from src.services.league.league_player_service import LeaguePlayerService
from src.utils.api_response import ApiResponse

league_player = Blueprint('league-player',__name__,url_prefix='/league-player')

service = LeaguePlayerService()

@league_player.post('/all/<league_id>')
async def get_many_router(league_id: str):
    try:
        data = await request.get_json()
        result = await service.get_many(league_id, data)
        
        return await ApiResponse.payload([p.to_json() for p in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
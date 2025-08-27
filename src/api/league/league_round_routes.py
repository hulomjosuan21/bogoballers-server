from quart import Blueprint, request
from src.services.league.league_round_service import LeagueRoundService
from src.utils.api_response import ApiResponse

round_bp = Blueprint('round', __name__, url_prefix="/league/round")

service = LeagueRoundService()

@round_bp.put('/<round_id>')
async def update_route(round_id: str):
    try:
        data = await request.get_json()
        result = await service.update(round_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
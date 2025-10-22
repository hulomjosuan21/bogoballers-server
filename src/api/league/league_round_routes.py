import traceback
from quart import Blueprint, request
from src.services.league.league_round_service import LeagueRoundService
from src.utils.api_response import ApiException, ApiResponse

round_bp = Blueprint('round', __name__, url_prefix="/league-round")

service = LeagueRoundService()

@round_bp.post("/double-elim/<league_id>/<round_id>/progress-stage")
async def progress_stage_route(league_id: str, round_id: str):
    try:
        matches = await service.progress_double_elim_stage(league_id, round_id)
        return await ApiResponse.success(message=f"generated: {len(matches)}")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@round_bp.put('/progression/<round_id>')
async def progression_route(round_id: str):
    try:
        data = await request.get_json()
        result = await service.round_progression(round_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
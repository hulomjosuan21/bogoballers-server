import traceback
from quart import Blueprint, request
from src.services.match.match_service import LeagueMatchService
from src.utils.api_response import ApiResponse

league_match_bp = Blueprint('league-match', __name__, url_prefix='/league-match')

service = LeagueMatchService()

@league_match_bp.post('/generate/elimination/<elimination_round_id>')
async def generate_elimination_round_route(elimination_round_id: str):
    try:
        result = await service.generate_first_elimination_round(elimination_round_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.post('/generate/progress-next/<current_round_id>/<next_round_id>')
async def progress_next_round_route(current_round_id: str, next_round_id: str):
    try:
        result = await service.progress_to_next_round(current_round_id, next_round_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.post('/generate/finalize/<final_round_id>')
async def finalize_tournament_results_route(final_round_id: str):
    try:
        result = await service.finalize_tournament_results(final_round_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
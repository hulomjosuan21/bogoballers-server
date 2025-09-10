import traceback
from quart import Blueprint

from src.services.match.match_service import MatchService
from src.utils.api_response import ApiResponse

league_match_bp = Blueprint('league-match', __name__, url_prefix='/league-match')

service = MatchService()

@league_match_bp.post('/generate/<round_id>')
async def generate_matches_route(round_id: str):
    try:
        result = await service.generate_and_save_matches(round_id=round_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
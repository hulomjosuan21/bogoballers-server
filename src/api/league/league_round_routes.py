import traceback
from quart import Blueprint, request
from src.services.league.league_round_service import LeagueRoundService
from src.utils.api_response import ApiException, ApiResponse

round_bp = Blueprint('round', __name__, url_prefix="/league-round")

service = LeagueRoundService()

@round_bp.post("/<league_category_id>/save-changes")
async def save_changes_route(league_category_id: str):
    try:
        data = await request.get_json()
        if not data or "operations" not in data:
            raise ApiException("Missing 'operations' in request body")
        operations = data["operations"]
        
        for i, op in enumerate(operations):
            print(f"Operation {i+1}: {op.get('type')} - {op.get('data', {})}")
        
        message, _ = await service.save_changes(league_category_id, operations)
        return await ApiResponse.success(message=message)
    except Exception as e:
        return await ApiResponse.error(e)
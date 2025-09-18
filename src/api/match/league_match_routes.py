import traceback
from quart import Blueprint, jsonify, request
from src.services.redis_service import RedisService
from src.services.match.match_service import LeagueMatchService
from src.utils.api_response import ApiResponse

league_match_bp = Blueprint('league-match', __name__, url_prefix='/league-match')
redis_service = RedisService()
@league_match_bp.get('/<string:match_id>/live')
async def get_live_match_state(match_id:str):
    room_name = f"match_room_{match_id}"
    latest_state = await redis_service.get_state(room_name)
    
    if latest_state:
        return jsonify({ "present": latest_state, "past": [], "future": [] })
    else:
        return jsonify({"error": "Live match has not started or state not found in Redis"}), 404
    
service = LeagueMatchService()

@league_match_bp.put('/<league_round_id>')
async def get_update_one_route(league_round_id: str):
    try:
        data = await request.get_json()
        result = await service.update_one(league_round_id,data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_match_bp.post('/all/<league_category_id>/<round_id>')
async def get_many_route(league_category_id: str, round_id: str):
    try:
        data = await request.get_json()
        result = await service.get_many(league_category_id,round_id,data)
        return await ApiResponse.payload([r.to_json() for r in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@league_match_bp.post('/generate/elimination/<league_id>/<elimination_round_id>')
async def generate_elimination_round_route(league_id: str,elimination_round_id: str):
    try:
        result = await service.generate_first_elimination_round(league_id, elimination_round_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_match_bp.post('/generate/progress-next/<league_id>/<current_round_id>/<next_round_id>')
async def progress_next_round_route(league_id: str, current_round_id: str, next_round_id: str):
    try:
        result = await service.progress_to_next_round(league_id, current_round_id, next_round_id)
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
    
@league_match_bp.get('/<league_match_id>')
async def get_one_route(league_match_id: str):
    try:
        result = await service.get_one(league_match_id)
        return await ApiResponse.payload(result.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    

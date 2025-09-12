import traceback
from quart import Blueprint, request
from quart_auth import login_required, current_user
from src.services.league.league_service import LeagueService
from src.utils.api_response import ApiResponse

league_bp = Blueprint("league", __name__, url_prefix="/league")

service = LeagueService()

@league_bp.get('/analytics/<league_id>')
async def league_analytics_route(league_id: str):
    try:
       result = await service.analytics(league_id=league_id)
       return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_bp.post('/create-new')
@login_required
async def create_new_league_route():
    try:
        form = await request.form
        files = await request.files
        user_id = current_user.auth_id
        result = await service.create_one(user_id, form, files)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_bp.post('/active')
async def get_one_route():
    try:
        data = await request.get_json()
        user_id = request.args.get('user_id') or current_user.auth_id
        result = await service.get_one(user_id, data)
        return await ApiResponse.payload(result.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
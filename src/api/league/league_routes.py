import traceback
from quart import Blueprint, request
from quart_auth import login_required, current_user
from src.services.league.league_service import LeagueService
from src.utils.api_response import ApiResponse

league_bp = Blueprint("league", __name__, url_prefix="/league")

service = LeagueService()

@league_bp.post('/<public_league_id>/public-view')
async def get_one_by_public_id(public_league_id: str):
    try:
        data = await request.get_json()
        result = await service.get_one_by_public_id(public_league_id, data)
        return await ApiResponse.payload(result.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_bp.put('/<league_id>/update')
async def update_one_route(league_id: str):
    try:
        data = await request.get_json()
        if not data:
            return await ApiResponse.success(message="No changes")
        result = await service.edit_one(league_id,data)
        return await ApiResponse.success(message=result)        
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

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
    
@league_bp.put("/<string:league_id>/update-field/<string:field_name>")
async def update_league_route(league_id: str, field_name: str):
    try:
        form = await request.form
        files = await request.files
        
        json_data = form.get(field_name)
        result = await service.update_league_resource(league_id, field_name, json_data, files)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
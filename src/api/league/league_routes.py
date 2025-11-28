import traceback
from quart import Blueprint, jsonify, request
from quart_auth import login_required, current_user
from src.extensions import AsyncSession
from src.services.league.league_service import LeagueService
from src.utils.api_response import ApiResponse

league_bp = Blueprint("league", __name__, url_prefix="/league")

service = LeagueService()

@league_bp.get('/participation')
async def fetch_participation():
    try:
        user_id = request.args.get('user_id', None)
        player_id = request.args.get('player_id', None)
        result = await service.fetch_participation(user_id=user_id,player_id=player_id)
        
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@league_bp.get('/carousel')
async def fetch_carousel():
    try:
        return await service.fetch_carousel()
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e) 

@league_bp.get('/print/<league_id>')
async def print_league(league_id: str):
    try:
        return await service.print_league(league_id)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e) 

@league_bp.get('/fetch')
async def fetch_league():
    try:
        user_id = request.args.get('user_id') or current_user.auth_id
        param_status_list = request.args.getlist('status')
        param_filter = request.args.get('filter', None)
        param_all = request.args.get('all', 'false').lower() == 'true'
        param_active = request.args.get('active', 'false').lower() == 'true'
        param_public_league_id = request.args.get('public_league_id', None)
        
        result = await service.fetch_generic(user_id=user_id,
                                             param_status_list=param_status_list,
                                             param_filter=param_filter,
                                             param_public_league_id=param_public_league_id,
                                             param_all=param_all,
                                             param_active=param_active)
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)        

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
    
@league_bp.get('/logs')
async def get_logs():
    league_id = request.args.get('league_id')
    round_id = request.args.get('round_id')
    team_id = request.args.get('team_id')
    logs = await service.get_logs(
        league_id=league_id,
        round_id=round_id,
        team_id=team_id
    )
    
    return jsonify({
        "status": "success",
        "data": [
            {
                "id": log.league_log_id,
                "action": log.action_type,
                "message": log.message,
                "meta": log.meta_data,
                "created_at": log.log_created_at.isoformat()
            } 
            for log in logs
        ]
    })
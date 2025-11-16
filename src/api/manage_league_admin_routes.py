import traceback
from quart import Blueprint, jsonify, request
from src.services.manage_league_admins import ManageLeagueAdministratorService
from src.utils.api_response import ApiException, ApiResponse

manage_league_admin_bp = Blueprint('manage-league-admins', __name__, url_prefix='/manage-league-admins')

service = ManageLeagueAdministratorService()

@manage_league_admin_bp.get('/all-admins')
async def get_all_admins():
    try:
        admins = await service.get_all_administrators()
        return await ApiResponse.payload([admin.to_json() for admin in admins])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@manage_league_admin_bp.get('/all-leagues')
async def get_all_leagues():
    try:
        leagues = await service.get_all_leagues()
        return await ApiResponse.payload([league.to_json(include_team=False) for league in leagues])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@manage_league_admin_bp.patch('/admin/<string:league_administrator_id>/toggle-operational')
async def toggle_admin_operational(league_administrator_id: str):
    try:
        admin = await service.toggle_admin_operational(league_administrator_id=league_administrator_id)
        if not admin:
            raise ApiException("League administrator not found")
        
        return await ApiResponse.payload(admin.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@manage_league_admin_bp.patch('/league/<string:league_id>/update-status')
async def update_league_status(league_id: str):
    try:
        data = await request.get_json()
        new_status = data.get('status')

        if not new_status:
            raise ApiException("Missing 'status' in request body")

        league = await service.update_league_status(league_id=league_id, new_status=new_status)
        if not league:
            raise ApiException("League not found")
            
        return await ApiResponse.payload(league.to_json(include_team=False))
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
from quart import Blueprint, jsonify, request
from src.services.manage_league_admins import ManageLeagueAdministratorService

manage_league_admin_bp = Blueprint('manage-league-admins', __name__, url_prefix='/manage-league-admins')

service = ManageLeagueAdministratorService()

@manage_league_admin_bp.get('/all-admins')
async def get_all_admins():
    admins = await service.get_all_administrators()
    return jsonify([admin.to_json() for admin in admins]), 200

@manage_league_admin_bp.get('/all-leagues')
async def get_all_leagues():

    leagues = await service.get_all_leagues()
    return jsonify([league.to_json(include_team=False) for league in leagues]), 200

@manage_league_admin_bp.patch('/admin/<string:league_administrator_id>/toggle-operational')
async def toggle_admin_operational(league_administrator_id: str):
    admin = await service.toggle_admin_operational(league_administrator_id=league_administrator_id)
    if not admin:
        return jsonify({"message": "League administrator not found"}), 404
    
    return jsonify(admin.to_json()), 200

@manage_league_admin_bp.patch('/league/<string:league_id>/update-status')
async def update_league_status(league_id: str):

    data = await request.get_json()
    new_status = data.get('status')

    if not new_status:
        return jsonify({"message": "Missing 'status' in request body"}), 400

    league = await service.update_league_status(league_id=league_id, new_status=new_status)
    if not league:
        return jsonify({"message": "League not found"}), 404
        
    return jsonify(league.to_json(include_team=False)), 200
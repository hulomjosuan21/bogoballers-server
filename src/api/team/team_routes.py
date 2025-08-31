import traceback
from quart import Blueprint, request
from quart_auth import login_required, current_user
from src.utils.api_response import ApiException, ApiResponse
from src.services.team.team_service import TeamService

team_bp = Blueprint('team', __name__, url_prefix="/team")

service = TeamService()

@team_bp.get('/<team_id>')
async def get_one_route(team_id: str):
    try:
        if not team_id:
            raise ApiException("No team found")
        
        result = await service.get_team_with_players(team_id=team_id)
        return await ApiResponse.payload(result.to_json_for_team_manager())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
    
@team_bp.post('/create')
@login_required
async def create_one_route():
    try:
        user_id = request.args.get("user_id") or current_user.auth_id

        form = await request.form
        files = await request.files
        logo_file = files.get("team_logo") or form.get("team_logo")

        result = await service.create_one(user_id, form, logo_file)
        return await ApiResponse.success(
            message=result,
            status_code=201
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@team_bp.post('/create-many')
async def create_many_route():
    try:
        data = await request.get_json()
        result = await service.create_many(teams=data)
        return await ApiResponse.success(
            message=result,
            status_code=201
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@team_bp.delete('/delete/<team_id>')
async def delete_one_route(team_id: str):
    try:
        result = await service.delete_one(team_id)
        return await ApiResponse.success(
            message=result,
            status_code=200
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@team_bp.get('/all')
# @login_required
async def get_many_route():
    try:
        user_id = request.args.get("user_id") or current_user.auth_id
        
        result = await service.get_many(user_id)
        return await ApiResponse.payload([team.to_json_for_team_manager() for team in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@team_bp.get('/all-or')
async def fetch_many_route():
    try:
        search = request.args.get("search", None)
        result = await service.fetch_many(search)
        return await ApiResponse.payload(payload=result)
    except:
        traceback.print_exc()
        return await ApiResponse.payload(payload=[])
    
@team_bp.put('/update/<team_id>')
async def update_one_route(team_id: str):
    try:
        data = await request.get_json()
        if not team_id:
            raise ApiException("No team found.")
        result = await service.update_one(team_id=team_id, data=data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
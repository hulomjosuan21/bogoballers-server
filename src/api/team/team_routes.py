import traceback
from quart import Blueprint, request
from quart_auth import login_required, current_user
from src.utils.api_response import ApiResponse
from src.services.team.team_service import TeamService

team_bp = Blueprint('team', __name__, url_prefix="/team")

service = TeamService()

@team_bp.post('/create')
@login_required
async def create_route():
    try:
        user_id = request.args.get("user_id")

        form = await request.form
        files = await request.files
        logo_file = files.get("team_logo") or form.get("team_logo")

        effective_user_id = user_id if user_id else current_user.auth_id
        
        result = await service.create(effective_user_id, form, logo_file)
        return await ApiResponse.success(
            message=result,
            status_code=201
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@team_bp.delete('/delete/<team_id>')
@login_required
async def delete_route(team_id: str):
    try:
        user_id = current_user.auth_id
        result = await service.delete(team_id, user_id)
        return await ApiResponse.success(
            message=result,
            status_code=200
        )
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@team_bp.get('/all')
@login_required
async def get_many_route():
    try:
        user_id = request.args.get("user_id")
        effective_user_id = user_id if user_id else current_user.auth_id
        
        result = await service.get_many(effective_user_id)
        return await ApiResponse.payload(result)
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
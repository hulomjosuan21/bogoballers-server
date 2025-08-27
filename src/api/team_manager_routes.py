import traceback
from quart import Blueprint, request
from quart_auth import login_required, current_user
from src.utils.api_response import ApiResponse
from src.services.team_manager_service import TeamManagerService

team_mananger_bp = Blueprint("team_manager", __name__, url_prefix="/team-manager")

service = TeamManagerService()

@team_mananger_bp.post('/create')
async def create_route():
    try:
        data = await request.get_json()
        
        email = data.get("email")
        password_str = data.get("password_str")
        contact_number = data.get("contact_number")
        display_name = data.get("display_name")
        
        result = await service.create(email, password_str, contact_number, display_name)
        return await ApiResponse.success(message=result, status_code=201)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@team_mananger_bp.get('/auth')
@login_required
async def auth_route():
    try:
        user_id = request.args.get("user_id")
        payload = await service.get_authenticated_user(user_id, current_user.auth_id)
        return await ApiResponse.payload(payload)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
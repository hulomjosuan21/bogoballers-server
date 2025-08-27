from quart import Blueprint, request
from quart_auth import current_user, login_required
from src.utils.api_response import ApiResponse
from src.services.player.player_service import PlayerService

player_bp = Blueprint('player', __name__, url_prefix='/player')

service = PlayerService()

@player_bp.post('/create')
async def create_route():
    try:
        form = await request.form
        file = (await request.files).get("profile_image")
        
        result = await service.create(form, file)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)

@player_bp.get('/auth')
@login_required
async def auth_route():
    try:
        user_id = request.args.get("user_id")
        payload = await service.get_authenticated_player(user_id, current_user.auth_id)
        return await ApiResponse.payload(payload)
    except Exception as e:
        return await ApiResponse.error(e)

@player_bp.get('/all')
async def get_many_route():
    try:
        search = request.args.get("search", None)
        result = await service.get_many(search)
        return await ApiResponse.payload(payload=result)
    except Exception as e:
        print(f"Error in get_players: {e}")
        return await ApiResponse.payload(payload=[])
from typing import Optional
from quart import Blueprint, request
from quart_auth import current_user, login_required
from src.utils.api_response import ApiResponse
from src.services.player.player_service import PlayerService

player_bp = Blueprint('player', __name__, url_prefix='/player')

service = PlayerService()

@player_bp.post('/create')
async def create__one_route():
    try:
        form = await request.form
        file = (await request.files).get("profile_image")
        
        result = await service.create_one(form, file)
        return await ApiResponse.success(message=result)
    except Exception as e:
        return await ApiResponse.error(e)
    
@player_bp.post('/create-many')
async def create_many_route():
    try:
        data = await request.get_json()
        result = await service.create_many(players=data)
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
async def get_all_route():
    try:
        result = await service.get_all_players()

        players_data = [p.to_json() for p in result]
        return await ApiResponse.payload(players_data)
    except Exception as e:
        return await ApiResponse.error(e)
    
@player_bp.get('/leaderboard')
async def get_leaderboard():
    try:
        result = await service.get_player_leaderboard()
        players_data = [p.to_json() for p in result]
        return await ApiResponse.payload(players_data)
    except Exception as e:
        return await ApiResponse.error(e)
import traceback
from typing import Optional
from quart import Blueprint, request
from quart_auth import current_user, login_required
from src.services.player.player_upload_doc_service import PlayerUploadDocService
from src.utils.api_response import ApiResponse
from src.services.player.player_service import PlayerService

player_bp = Blueprint('player', __name__, url_prefix='/player')

service = PlayerService()
upload_service = PlayerUploadDocService()

@player_bp.post("/upload-doc/<player_id>")
async def upload_doc(player_id: str):
    try:
        result = await upload_service.upload(player_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@player_bp.post('/create')
async def create_one_route():
    try:
        form = await request.form
        file = (await request.files).get("profile_image")
        
        base_url = f"{request.scheme}://{request.host}"
        
        result = await service.create_one(form, file, base_url)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
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
        traceback.print_exc()
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
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@player_bp.post('/insert-ocuments-for-all')
async def insert_documents_for_all_players_route():
    try:
        data = await request.get_json()
        result = await service.insert_documents_for_all_players(documents_json=data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
import traceback
from quart import Blueprint, request
from quart_auth import current_user, login_required
from src.services.entity_service import EntityService
from src.utils.api_response import ApiResponse, ApiException

entity_bp = Blueprint("entity", __name__, url_prefix="/entity")
service = EntityService()

@entity_bp.post("/login")
async def login_route():
    try:
        form = await request.form
        result = await service.login(form)
        user = result["user"]
        access_token = result["access_token"]

        if user.account_type == "Team_Manager":
            return await ApiResponse.success(
                redirect="/team-manager/main/screen",
                payload=access_token
            )
        elif user.account_type == "Player":
            return await ApiResponse.success(
                redirect="/player/main/screen",
                payload=access_token
            )
        raise ApiException("Unauthorized account type")
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@entity_bp.get("/auth")
@login_required
async def get_current_user_route():
    try:
        user_id = request.args.get("user_id")
        user = await service.get_current_user(user_id=user_id, current_user=current_user)

        if user.account_type == "Team_Manager":
            return await ApiResponse.payload('team_manager')
        elif user.account_type == "Player":
            return await ApiResponse.payload('player')
        raise ApiException("Unauthorized account type", 400)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@entity_bp.post("/update-fcm")
@login_required
async def update_fcm_route():
    try:
        data = await request.get_json()
        fcm_token = data.get("fcm_token")
        if not fcm_token:
            raise ApiException("Missing FCM token")
        result = await service.update_fcm(fcm_token=fcm_token, current_user=current_user)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)
    
@entity_bp.post('/search')
async def search_entity_route():
    try:
        data = await request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return await ApiResponse.error("Query parameter is required")
        
        result = await service.search_entity(query)
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))
import traceback
from limits import RateLimitItemPerSecond
from quart import Blueprint, request
from quart_auth import current_user, login_required
from src.services.entity_service import EntityService
from src.utils.api_response import ApiResponse, ApiException
from src.limiter import enforce_rate_limit, limiter

entity_bp = Blueprint("entity", __name__, url_prefix="/entity")
service = EntityService()

@entity_bp.post("/login")
async def login_route():
    try:
        data = await request.get_json()
        result = await service.login(data)
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
    
search_limit = RateLimitItemPerSecond(2)
    
@entity_bp.post('/search')
async def search_entity_route():
    try:
        await enforce_rate_limit(request, search_limit, key_prefix="search")
        data = await request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            raise ApiException("Query parameter is required")
        
        result = await service.search_entity(query)
        return await ApiResponse.payload(result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))
    
@entity_bp.put("/update/image/<entity_id>/<account_type>")
async def update_image_route(entity_id: str, account_type: str):
    try:
        form = await request.form
        files = await request.files
        
        file = files.get("new_image")

        if file:
            file_or_url = file
        else:
            file_or_url = form.get("new_image")

        if not file_or_url:
            return await ApiResponse.error("No file or URL provided")

        await EntityService.update_image(file_or_url, entity_id, account_type)

        return await ApiResponse.success(message="Update successfully.")

    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(str(e))

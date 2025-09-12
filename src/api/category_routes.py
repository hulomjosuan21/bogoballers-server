import json
import traceback
from quart import Blueprint, request
from quart_auth import current_user, login_required
from src.services.category_service import CategoryService
from src.utils.api_response import ApiException, ApiResponse
from src.utils.server_utils import validate_required_fields

category_bp = Blueprint("category", __name__, url_prefix="/category")

service = CategoryService()

@category_bp.get("/all")
async def get_all_route():
    try:
        user_id = request.args.get("user_id") or current_user.auth_id
        if not user_id:
            raise ApiException("No user found.")
        result = await service.get_all(user_id=user_id)
        return await ApiResponse.payload([c.to_json() for c in result])
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@category_bp.get("/<category_id>")
async def get_one_route(category_id: str):
    try:
        result = await service.get_one(category_id)
        return await ApiResponse.payload(result.to_json())
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@category_bp.post("/<league_administrator_id>")
@login_required
async def create_one_route(league_administrator_id: str):
    try:
        data = await request.get_json()
        result = await service.create_one(league_administrator_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@category_bp.put("/<category_id>")
async def update_one_route(category_id: str):
    try:
        data = await request.get_json()
        result = await service.edit_one(category_id, data)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)

@category_bp.delete("/<category_id>")
async def delete_one_route(category_id: str):
    try:
        result = await service.delete_one(category_id)
        return await ApiResponse.success(message=result)
    except Exception as e:
        traceback.print_exc()
        return await ApiResponse.error(e)